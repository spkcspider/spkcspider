__all__ = (
    "create_b64_token", "create_b64_id_token", "get_settings_func",
    "extract_app_dicts", "add_by_field", "prepare_description",
    "merge_get_url", "add_property", "is_decimal",
    "extract_host", "get_hashob", "aesgcm_scrypt_cryptor",
    "aesgcm_pbkdf2_cryptor", "get_requests_params"
)


import os
import re
import base64
import logging
import inspect
from hashlib import pbkdf2_hmac
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

from functools import lru_cache
from importlib import import_module

from rdflib import Literal, BNode, XSD, RDF

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_bytes

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .constants import MAX_TOKEN_SIZE, spkcgraph, host_tld_matcher

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
def get_settings_func(name, default):
    filterpath = getattr(
        settings, name,
        default
    )
    if callable(filterpath):
        return filterpath
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
    ret = urlunsplit((*urlparsed[:3], urlencode(GET), ""))
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
    return mapper.get(
        _url["host"],
        mapper.get(
            _url["tld"],  # maybe None but then fall to retrieval 3
            mapper[b"default"]
        )
    )
