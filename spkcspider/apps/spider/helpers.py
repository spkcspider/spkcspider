__all__ = (
    "create_b64_token", "create_b64_id_token", "get_settings_func",
    "extract_app_dicts", "add_by_field", "prepare_description",
    "merge_get_url", "add_property", "is_decimal",
    "extract_host", "get_hashob", "aesgcm_scrypt_cryptor",
    "aesgcm_pbkdf2_cryptor", "get_requests_params",
    "literalize", "field_to_python", "calculate_protection_strength"
)


import os
import re
import base64
import logging
import inspect
from statistics import mean

from hashlib import pbkdf2_hmac
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode, urljoin

from functools import lru_cache
from importlib import import_module

from rdflib import Literal, BNode, XSD, RDF, URIRef

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_bytes
from django.forms import BoundField, Field

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from spkcspider.constants import (
    MAX_TOKEN_SIZE, spkcgraph, host_tld_matcher, ProtectionStateType
)

# for not spamming sets
_empty_set = frozenset()
# for not spamming dicts
_empty_dict = dict()

_pbkdf2_params = {
    "iterations": 120000,
    "hash_name": "sha512",
    "dklen": 32
}

_Scrypt_params = {
    "length": 32,
    "n": 2**14,
    "r": 16,
    "p": 2
}


def get_hashob():
    return hashes.Hash(
        settings.SPIDER_HASH_ALGORITHM, backend=default_backend()
    )


def aesgcm_scrypt_cryptor(pw, salt=None, params=_Scrypt_params):
    if salt is None:
        salt = settings.SECRET_KEY
    salt = force_bytes(salt)

    return AESGCM(
        Scrypt(
            salt=salt,
            backend=default_backend(),
            **params
        ).derive(pw[:128].encode("utf-8"))
    )


def aesgcm_pbkdf2_cryptor(pw, salt=None, params=_pbkdf2_params):
    if salt is None:
        salt = settings.SECRET_KEY
    salt = force_bytes(salt)

    return AESGCM(
        pbkdf2_hmac(
            password=pw[:128].encode("utf-8"),
            salt=salt,
            **params
        )
    )


def is_decimal(inp, precision=None, allow_sign=False):
    prec_start = None
    if len(inp) == 0:
        return False
    if inp[0] == "-" and allow_sign:
        inp = inp[1:]
    for count, i in enumerate(inp):
        if i == "." and prec_start is None:
            prec_start = count
        elif not i.isdigit():
            return False
    return (
        None in (precision, prec_start) or len(inp)-prec_start-1 <= precision
    )


def calculate_protection_strength(required_passes, protections=None):
    prot_strength = None
    max_prot_strength = 0
    if protections:
        # instant fail strength
        fail_strength = 0
        amount = 0
        # regular protections strength
        strengths = []
        for protection in protections:
            state = protection.cleaned_data.get(
                "state", ProtectionStateType.disabled
            )
            if state == ProtectionStateType.disabled:
                continue
            if not protection.is_valid():
                continue

            if len(str(protection.cleaned_data)) > 100000:
                raise ValidationError(
                    _("Protection >100 kb: %(name)s"),
                    params={"name": protection}
                )
            if state == ProtectionStateType.instant_fail:
                s = protection.get_strength()
                if s[1] > max_prot_strength:
                    max_prot_strength = s[1]
                fail_strength = max(
                    fail_strength, s[0]
                )
            else:
                s = protection.get_strength()
                if s[1] > max_prot_strength:
                    max_prot_strength = s[1]
                strengths.append(s[0])
            amount += 1
        strengths.sort()
        if required_passes > 0:
            if amount == 0:
                # login or token only
                # not 10 because 10 is also used for uniqueness
                prot_strength = 4
            else:
                # avg strength but maximal 3,
                # (4 can appear because of component auth)
                # clamp
                prot_strength = min(round(mean(
                    strengths[:required_passes]
                )), 3)
        else:
            prot_strength = 0
        prot_strength = max(prot_strength, fail_strength)
    return (prot_strength, max_prot_strength)


def field_to_python(value):
    if isinstance(value, BoundField):
        data = value.initial
        if value.form.is_bound:
            value = value.field.bound_data(value.data, data)
        else:
            value = data
    return value


def literalize(
    ob=None, datatype=None, use_uriref=None, domain_base=""
):
    if isinstance(ob, BoundField):
        if not datatype:
            datatype = getattr(ob.field, "spkc_datatype", None)
        if use_uriref is None:
            use_uriref = getattr(ob.field, "spkc_use_uriref", None)
        ob = field_to_python(ob)
    elif isinstance(datatype, BoundField):
        if use_uriref is None:
            use_uriref = getattr(datatype.field, "spkc_use_uriref", None)
        datatype = getattr(datatype.field, "spkc_datatype", None)
    elif isinstance(datatype, Field):
        if use_uriref is None:
            use_uriref = getattr(datatype, "spkc_use_uriref", None)
        datatype = getattr(datatype, "spkc_datatype", None)
    if ob is None:
        return RDF.nil
    if hasattr(ob, "get_absolute_url"):
        if not datatype:
            datatype = spkcgraph["hashableURI"]
        if use_uriref is None:
            use_uriref = True
        ob = ob.get_absolute_url()
    elif isinstance(ob, str) and not datatype:
        datatype = XSD.string
    if use_uriref:
        return URIRef(urljoin(domain_base, ob))
    return Literal(ob, datatype=datatype)


def add_property(
    graph, name, ref=None, ob=None, literal=None, datatype=None,
    iterate=False
):
    value_node = BNode()
    if ref:
        graph.add((
            ref, spkcgraph["properties"],
            value_node
        ))
    graph.add((
        value_node, spkcgraph["name"],
        Literal(name, datatype=XSD.string)
    ))
    if literal is None:
        literal = getattr(ob, name)
    if not iterate:
        literal = [literal]
    for l in literal:
        graph.add((
            value_node, spkcgraph["value"],
            Literal(l, datatype=datatype)
        ))
    if not literal:
        graph.set((value_node, spkcgraph["value"], RDF.nil))
    return value_node


@lru_cache(maxsize=None)
def get_settings_func(*args, default=None, exclude=frozenset()):
    if default is None:
        names, default = args[:-1], args[-1]
    filterpath = None
    for name in names:
        if getattr(settings, name, None) is not None:
            filterpath = getattr(settings, name)
            break
    if filterpath is None:
        filterpath = default
    # note: cannot distinguish between False and 0 and True and 1
    if filterpath in exclude:
        raise ValueError("invalid setting")
    if callable(filterpath):
        return filterpath
    elif isinstance(filterpath, bool):
        return lambda *args, **kwargs: filterpath
    else:
        module, name = filterpath.rsplit(".", 1)
        return getattr(import_module(module), name)


def add_by_field(dic, field="__name__"):
    def _func(klass):
        # should be able to block real object
        if "{}.{}".format(klass.__module__, klass.__qualname__) not in getattr(
            settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
        ):
            dic[getattr(klass, field)] = klass

        return klass
    return _func


def extract_app_dicts(app, name, fieldname=None):
    ndic = {}
    for (key, value) in getattr(app, name, _empty_dict).items():
        if inspect.isclass(value):
            if "{}.{}".format(
                value.__module__, value.__qualname__
            ) not in getattr(
                settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
            ):
                if fieldname:
                    setattr(value, fieldname, key)
                ndic[key] = value
        else:
            # set None if Module is not always available
            if value and value not in getattr(
                settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
            ):
                module, name = value.rsplit(".", 1)
                value = getattr(import_module(module), name)
                if fieldname:
                    setattr(value, fieldname, key)
                ndic[key] = value
    return ndic


def create_b64_token(size=None):
    if not size:
        from django.conf import settings
        size = getattr(settings, "TOKEN_SIZE", 30)
    if size > MAX_TOKEN_SIZE:
        logging.warning("Nonce too big")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii').rstrip("=")


def create_b64_id_token(id, sep="_", size=None):
    return sep.join((hex(id)[2:], create_b64_token(size)))


_cleanstr = re.compile(r'<+.*>+')
_whitespsplit = re.compile(r'\s+')


def prepare_description(raw_html, amount=0):
    text = _cleanstr.sub(' ', raw_html).\
        replace("<", " ").replace(">", " ").strip()
    return _whitespsplit.split(text, amount)


_check_scheme = re.compile(r'^[a-z]+://', re.I)


def extract_host(url):
    url = url.lstrip(":/")
    if _check_scheme.search(url) is None:
        urlparsed = urlsplit("://".join(("https", url)))
    else:
        urlparsed = urlsplit(url)
    return "://".join(urlparsed[:2])


def merge_get_url(_url, **kwargs):
    if not _url.isprintable():
        raise ValidationError(
            _("Url contains control characters"),
            code="control_characters"
        )
    _url = _url.lstrip(":/")
    if _check_scheme.search(_url) is None:
        urlparsed = urlsplit("://".join(("https", _url)))
    else:
        urlparsed = urlsplit(_url)
    _strip = []
    for i in kwargs.keys():
        if not kwargs[i]:
            _strip.append(i)
    GET = parse_qs(urlparsed.query)
    GET.update(kwargs)
    for item in _strip:
        GET.pop(item, None)
    ret = urlunsplit((*urlparsed[:3], urlencode(GET, doseq=True), ""))
    return ret


def get_requests_params(url):
    _url = host_tld_matcher.match(url)
    if not _url:
        raise ValidationError(
            _("Invalid URL: \"%(url)s\""),
            code="invalid_url",
            params={"url": url}
        )
    _url = _url.groupdict()
    mapper = settings.SPIDER_REQUEST_KWARGS_MAP
    return (
        mapper.get(
            _url["host"],
            mapper.get(
                _url["tld"],  # maybe None but then fall to retrieval 3
                mapper[b"default"]
            )
        ),
        get_settings_func(
            "SPIDER_INLINE",
            "spkcspider.apps.spider.functions.clean_spider_inline",
            exclude=frozenset({True})
        )(_url["host"])
    )
