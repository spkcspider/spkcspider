__all__ = [
    "verify_length"
]

from django.conf import settings


def verify_length(resp):
    if (
        "content-length" not in resp.headers or
        not resp.headers["content-length"].isdigit()
    ):
        return False
    if (
        settings.VERIFIER_MAX_SIZE_ACCEPTED <
        int(resp.headers["content-length"])
    ):
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
