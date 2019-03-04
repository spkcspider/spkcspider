__all__ = [
    "clean_graph", "get_hashob"
]


from django.conf import settings

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from rdflib import URIRef

from spkcspider.apps.spider.constants.static import spkcgraph


def validate_request_default(request, form):
    if not form.is_valid():
        return False

    return True


def verify_tag_default(tag):
    pass


def clean_graph(mtype, graph, start):
    if not mtype:
        return None
    elif mtype == "UserComponent":
        return "list"
    elif mtype == "SpiderTag":
        if (URIRef(start), spkcgraph["features"], "verify"):
            return "layout_cb"
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
