__all__ = ("token_nonce", "MAX_NONCE_SIZE", "cmp_pw")


import os
import base64
import logging

MAX_NONCE_SIZE = 90

if MAX_NONCE_SIZE % 3 != 0:
    raise Exception("MAX_NONCE_SIZE must be multiple of 3")


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
