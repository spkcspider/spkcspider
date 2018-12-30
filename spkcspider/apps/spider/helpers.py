__all__ = (
    "create_b64_token", "get_settings_func",
    "extract_app_dicts", "add_by_field", "prepare_description",
    "merge_get_url", "add_property"
)


import os
import re
import base64
import logging
import inspect
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

from functools import lru_cache
from importlib import import_module

from rdflib import Literal, BNode

from django.conf import settings
from .constants.static import MAX_NONCE_SIZE, spkcgraph

# for not spamming sets
_empty_set = frozenset()
# for not spamming dicts
_empty_dict = dict()


def add_property(graph, name, ref=None, ob=None, literal=None, datatype=None):
    value_node = BNode()
    if ref:
        graph.add((
            ref, spkcgraph["properties"],
            value_node
        ))
    graph.add((
        value_node, spkcgraph["name"],
        Literal(name)
    ))
    if not literal:
        literal = getattr(ob, name)
    graph.add((
        value_node, spkcgraph["value"],
        Literal(literal, datatype=datatype)
    ))
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
        if value is None:
            ndic[key] = value
        elif inspect.isclass(value):
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
        from .constants.settings import INITIAL_NONCE_SIZE
        size = int(INITIAL_NONCE_SIZE)
    if size > MAX_NONCE_SIZE:
        logging.warning("Nonce too big")
    if size % 3 != 0:
        raise Exception("SPIDER_NONCE_SIZE must be multiple of 3")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii')


_cleanstr = re.compile(r'<+.*>+')
_whitespsplit = re.compile(r'\s+')


def prepare_description(raw_html, amount=0):
    text = _cleanstr.sub(' ', raw_html).\
        replace("<", " ").replace(">", " ").strip()
    return _whitespsplit.split(text, amount)


def merge_get_url(_url, **kwargs):
    urlparsed = urlsplit(_url, scheme="https")
    _strip = []
    for i in kwargs.keys():
        if not kwargs[i]:
            _strip.append(i)
    GET = parse_qs(urlparsed.query)
    GET.update(kwargs)
    for item in _strip:
        GET.pop(item, None)
    ret = urlunsplit((*urlparsed[:3], urlencode(GET), ""))
    # work around url.parse bug 35377
    if not urlparsed[1]:
        ret = ret.replace(":///", "://", 1)
    return ret
