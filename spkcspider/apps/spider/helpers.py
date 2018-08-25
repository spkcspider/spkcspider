__all__ = (
    "token_nonce", "MAX_NONCE_SIZE", "ALLOW_ALL_FILTER_FUNC", "cmp_pw",
    "get_filterfunc", "url3"
)


import os
import base64
import logging
from functools import lru_cache
from importlib import import_module
import certifi
import urllib3
from django.conf import settings

MAX_NONCE_SIZE = 90

if MAX_NONCE_SIZE % 3 != 0:
    raise Exception("MAX_NONCE_SIZE must be multiple of 3")


def ALLOW_ALL_FILTER_FUNC(*args, **kwargs):
    return True


@lru_cache()
def get_filterfunc(name):
    filterpath = getattr(
        settings, name,
        "spkcspider.apps.spider.helpers.ALLOW_ALL_FILTER_FUNC"
    )
    if callable(filterpath):
        return filterpath
    else:
        module, name = filterpath.rsplit(".", 1)
        return getattr(import_module(module), name)


url3 = urllib3.PoolManager(
    cert_reqs='CERT_REQUIRED',
    ca_certs=certifi.where()
)


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
