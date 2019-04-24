__all__ = [
    "clean_graph", "get_hashob", "validate_request_default",
    "verify_tag_default", "domain_auth"
]

import logging
from urllib.parse import parse_qs, urlencode

from django.conf import settings
from django.urls import reverse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from rdflib import XSD, URIRef, Literal

import requests
import certifi

from spkcspider.apps.spider.constants import spkcgraph
from spkcspider.apps.spider.helpers import create_b64_token


def validate_request_default(request, form):
    if not form.is_valid():
        return False

    return True


def verify_tag_default(tag):
    tag.save()


def domain_auth(source, hostpart):
    GET = parse_qs(source.get_params)
    if "token" not in GET:
        GET["token"] = "prefer"
    GET["intention"] = "domain"
    GET["referrer"] = "{}{}".format(
        hostpart,
        reverse("spider_verifier:create")
    )
    source.update_secret = create_b64_token()
    source.save(update_fields=["update_secret"])
    GET["payload"] = urlencode(
        {
            "url": source.url,
            "update_secret": source.update_secret
        }
    )

    url = "{}?{}".format(
        source.url, urlencode(GET)
    )
    ret = True
    try:
        resp = requests.get(
            url, verify=certifi.where(),
            timeout=settings.VERIFIER_REQUESTS_TIMEOUT
        )
        resp.raise_for_status()
    except Exception:
        if settings.DEBUG:
            logging.exception("domain_auth failed")
        ret = False
    # other or own update_secret was successful or url has problems
    source.refresh_from_db()
    return ret


def clean_graph(mtype, graph, start, source, hostpart):
    if not mtype:
        return None
    elif "UserComponent" in mtype:
        return "list"
    elif "SpiderTag" in mtype:
        if (
            URIRef(start),
            spkcgraph["features"],
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
