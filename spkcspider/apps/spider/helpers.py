__all__ = (
    "token_nonce", "get_settings_func",
    "extract_app_dicts", "add_by_field", "prepare_description",
    "join_get_url"
)


import os
import re
import base64
import logging
import inspect
from urllib.parse import urlencode

from functools import lru_cache
from importlib import import_module
from django.conf import settings
from .constants.static import MAX_NONCE_SIZE

# for not spamming sets
_empty_set = frozenset()
# for not spamming dicts
_empty_dict = dict()


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
        if klass.__name__ not in getattr(
            settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
        ):
            dic[getattr(klass, field)] = klass

        return klass
    return _func


def extract_app_dicts(app, name, fieldname=None):
    ndic = {}
    for (key, value) in getattr(app, name, _empty_dict):
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


def token_nonce(size=None):
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


def join_get_url(url, **kwargs):
    getargs = "&".join(
        ["{}={}".format(i[0], urlencode(i[1])) for i in kwargs.items()]
    )
    if "?" in url:
        if url[-1] == "?":
            url = "{}{}".format(url, getargs)
        else:
            url = "{}&{}".format(url, getargs)
    else:
        url = "{}?{}".format(url, getargs)
    return url
