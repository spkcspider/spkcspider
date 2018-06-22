__all__ = ("token_nonce", "MAX_NONCE_SIZE")


import os
import base64
import logging
# from functools import lru_cache

MAX_NONCE_SIZE = 90

if MAX_NONCE_SIZE % 3 != 0:
    raise Exception("MAX_NONCE_SIZE must be multiple of 3")


def token_nonce(size=None):
    if not size:
        from .forms import INITIAL_NONCE_SIZE
        size = int(INITIAL_NONCE_SIZE)
    if size <= MAX_NONCE_SIZE:
        logging.warning("Nonce too big")
    if size % 3 != 0:
        raise Exception("SPIDER_NONCE_SIZE must be multiple of 3")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii')
