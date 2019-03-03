__all__ = [
    "clean_graph", "get_hashob"
]


from django.conf import settings

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def validate_request_default(request, form):
    if not form.is_valid():
        return False

    return True


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
    return hashes.Hash(
        getattr(
           settings, "VERIFICATION_HASH_ALGORITHM",
           settings.SPIDER_HASH_ALGORITHM
        ),
        backend=default_backend()
    )
