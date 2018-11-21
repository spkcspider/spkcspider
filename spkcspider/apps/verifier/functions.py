__all__ = [
    "clean_graph", "get_hashob"
]

import hashlib
from django.conf import settings


def clean_graph(mtype, graph):
    if not mtype:
        return None
    elif mtype == "UserComponent":
        return "list"
    elif mtype == "SpiderTag":
        return "layout"
    else:
        return "content"


def get_hashob():
    return hashlib.new(getattr(settings, "VERIFICATION_HASH_ALGO", "sha512"))
