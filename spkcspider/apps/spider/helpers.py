__all__ = (
    "token_nonce", "MAX_NONCE_SIZE", "cmp_pw", "get_settings_func",
    "extract_app_dicts", "add_by_field"
)


import os
import base64
import logging
import inspect

from functools import lru_cache
from importlib import import_module
from django.conf import settings

# for not spamming sets
_empty_set = frozenset()
# for not spamming dicts
_empty_dict = dict()

MAX_NONCE_SIZE = 90

if MAX_NONCE_SIZE % 3 != 0:
    raise Exception("MAX_NONCE_SIZE must be multiple of 3")


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
        from .forms import INITIAL_NONCE_SIZE
        size = int(INITIAL_NONCE_SIZE)
    if size > MAX_NONCE_SIZE:
        logging.warning("Nonce too big")
    if size % 3 != 0:
        raise Exception("SPIDER_NONCE_SIZE must be multiple of 3")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii')


def cmp_pw(pw_source, pw_user):
    error = False
    len_pw1 = len(pw_source)
    for i in range(0, len(pw_user)):
        if len_pw1 <= i:
            # fake
            pw_user[i] != pw_user[i]
            error = True
        elif pw_source[i] != pw_user[i]:
            error = True
    return (not error and len(pw_source) == len(pw_user))
