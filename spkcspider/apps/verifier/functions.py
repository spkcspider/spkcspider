__all__ = [
    "clean_graph", "get_hashob", "validate_request_default",
    "verify_tag_default", "domain_auth", "get_anchor_domain"
]

import functools
import logging
from urllib.parse import parse_qs, urlencode

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from rdflib import XSD, Literal, URIRef

from django.conf import settings
from django.test import Client
from django.urls import reverse
from spkcspider.constants import spkcgraph

from .conf import get_requests_params


@functools.lru_cache(1)
def get_anchor_domain():
    # if None, set to default Site ID if models are ready
    _anchor_domain = getattr(
        settings, "VERIFIER_ANCHOR_DOMAIN", getattr(
            settings, "SPIDER_ANCHOR_DOMAIN", None
        )
    )
    if _anchor_domain:
        return _anchor_domain
    from django.contrib.sites.models import Site
    return Site.objects.get(id=settings.SITE_ID).domain


def validate_request_default(request, form):
    if not form.is_valid():
        return False

    return True


def verify_tag_default(tag, hostpart, ffrom) -> bool:
    """ return True if callback should be fired (if possible) """
    return tag.verification_state == "verified"


def domain_auth(source, hostpart):
    GET = parse_qs(source.get_params)
    if "token" not in GET:
        GET["token"] = "prefer"
    GET["intention"] = "domain"
    GET["referrer"] = "{}{}".format(
        hostpart,
        reverse("spider_verifier:create")
    )
    source.initialize_token()
    source.save(update_fields=["token"])
    GET["payload"] = urlencode(
        {
            "url": source.url,
            "update_secret": source.token
        }
    )

    url = "{}?{}".format(
        source.url, urlencode(GET, doseq=True)
    )
    ret = True
    params, inline_domain = get_requests_params(url)

    if inline_domain:
        response = Client().head(
            url, follow=True, secure=True, Connection="close",
            SERVER_NAME=inline_domain
        )
        if response.status_code >= 400:
            ret = False
    else:
        try:
            with requests.head(
                url, headers={"Connection": "close"},
                **params
            ) as resp:
                resp.close()
                resp.raise_for_status()
        except Exception:
            if settings.DEBUG:
                logging.exception("domain_auth failed")
            ret = False
    # other or own update_secret was successful or url has problems
    source.refresh_from_db()
    return ret


def clean_graph(graph, start, source, hostpart):
    mtype = str(graph.value(
        subject=start, predicate=spkcgraph["type"], any=not settings.DEBUG
    ))
    if not mtype:
        return None
    elif "UserComponent" == mtype:
        return "list"
    elif "SpiderTag" == mtype:
        if (
            URIRef(start),
            spkcgraph["abilities"],
            Literal("verify", datatype=XSD.string)
        ) in graph:
            return "layout_cb"
        ret = "layout"
        if domain_auth(source, hostpart):
            graph.set(
                (
                    start,
                    spkcgraph["action:view"],
                    Literal(source.get_url(), datatype=XSD.anyURI)
                )
            )
            ret = "layout_cb"
        return ret
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
