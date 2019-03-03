__all__ = ("validate", "verify_download_size")

import logging
import binascii
import tempfile
import os

from django.utils.translation import gettext_lazy as _
from django.conf import settings

from rdflib import Graph, URIRef, Literal
from rdflib.namespace import XSD
import requests
import certifi

from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.helpers import merge_get_url, get_settings_func

from .constants import BUFFER_SIZE
from .functions import get_hashob
from .models import VerifySourceObject

hashable_predicates = set([spkcgraph["name"], spkcgraph["value"]])


def hash_entry(triple):
    h = get_hashob()
    if triple[2].datatype == XSD.base64Binary:
        h.update(triple[2].datatype.encode("utf8"))
        h.update(triple[2].toPython())
    else:
        if triple[2].datatype:
            h.update(triple[2].datatype.encode("utf8"))
        else:
            h.update(XSD.string.encode("utf8"))
        h.update(triple[2].encode("utf8"))
    return h.finalize()


def yield_hashes(graph, hashable_nodes):
    for t in graph.triples((None, spkcgraph["value"], None)):
        if (
            t[0] in hashable_nodes and
            t[2].datatype != spkcgraph["hashableURI"]
        ):
            yield hash_entry(t)


def yield_hashable_urls(graph, hashable_nodes):
    for t in graph.triples(
        (None, spkcgraph["value"], spkcgraph["hashableURI"])
    ):
        if t[0] in hashable_nodes:
            yield t


def verify_download_size(length, current_size=0):
    if not length or not length.isdigit():
        return False
    length = int(length)
    if settings.VERIFIER_MAX_SIZE_ACCEPTED < length:
        return False
    return True


def validate(ob):
    dvfile = None
    if isinstance(ob, tuple):
        dvfile = open(ob[0], "r+b")
        current_size = ob[1]
    else:
        current_size = 0
        dvfile = tempfile.mkstemp()

    if not dvfile:
        url = VerifySourceObject.objects.get(
            id=ob
        ).get_absolute_url()

        resp = requests.get(url, stream=True, verify=certifi.where())
        resp.raise_for_status()

        if not verify_download_size(
            resp.headers.get("content-length", None), current_size
        ):
            return
        current_size += int(resp.headers["content-length"])
        for chunk in resp.iter_content(BUFFER_SIZE):
            dvfile.write(chunk)
        dvfile.seek(0, 0)
    g = Graph()
    g.namespace_manager.bind("spkc", spkcgraph, replace=True)
    try:
        g.parse(
            dvfile.temporary_file_path(),
            format="turtle"
        )
        dvfile.close()
        os.unlink(dvfile.name)
    except Exception as exc:
        if settings.DEBUG:
            with open(
                dvfile.temporary_file_path()
            ) as f:
                logging.error(f.read())
        logging.exception(exc)
        return "invalid_format"

    tmp = list(g.triples((None, spkcgraph["scope"], None)))
    if len(tmp) != 1:
        return"invalid_graph"
    start = tmp[0][0]
    scope = tmp[0][2].toPython()
    tmp = list(g.triples((start, spkcgraph["pages.num_pages"], None)))
    if len(tmp) != 1:
        return "invalid_graph"
    pages = tmp[0][2].toPython()
    view_url = None
    if pages > 1:
        tmp = g.triples((start, spkcgraph["action:view"], None))
        if len(tmp) != 1:
            return "invalid_graph"
        view_url = tmp[0][2].toPython()
    mtype = None
    if scope == "list":
        mtype = "UserComponent"
    else:
        mtype = list(g.triples((
            start, spkcgraph["type"], None
        )))
        if len(mtype) > 0:
            mtype = mtype[0][2].value
        else:
            mtype = None

    data_type = get_settings_func(
        "VERIFIER_CLEAN_GRAPH",
        "spkcspider.apps.verifier.functions.clean_graph"
    )(mtype, g)
    if not data_type:
        return "invalid_type"

    # retrieve further pages
    for page in range(2, pages+1):
        url = merge_get_url(view_url, raw="embed", page=str(page))
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(url):
            return "insecure_url"
        try:
            resp = requests.get(url, stream=True, verify=certifi.where())
        except requests.exceptions.ConnectionError:
            return "invalid_url"
        if resp.status_code != 200:
            return "retrieval_failed"

        if not verify_download_size(
            resp.headers.get("content-length", None), current_size
        ):
            return "invalid_length"
        current_size += int(resp.headers["content-length"])
        self.cleaned_data["dvfile"] = TemporaryUploadedFile(
            "url_uploaded", resp.headers.get(
                'content-type', "application/octet-stream"
            ),
            int(resp.headers["content-length"]),
            "utf8"
        )

        for chunk in resp.iter_content(BUFFER_SIZE):
            self.cleaned_data["dvfile"].write(chunk)
        self.cleaned_data["dvfile"].seek(0, 0)
        try:
            g.parse(
                self.cleaned_data["dvfile"].temporary_file_path(),
                format="turtle"
            )
            self.cleaned_data["dvfile"].close()
            del self.cleaned_data["dvfile"]
        except Exception as exc:
            if settings.DEBUG:
                with open(
                    self.cleaned_data["dvfile"].temporary_file_path()
                ) as f:
                    logging.error(f.read())
            logging.exception(exc)
            # pages could have changed, but still incorrect
            raise forms.ValidationError(
                _("%(page)s is not a \"%(format)s\" file"),
                params={"format": "turtle", "page": page},
                code="invalid_file"
            )

    hashable_nodes = set(g.subjects(
        predicate=spkcgraph["hashable"], object=Literal(True)
    ))

    hashes = [
        i for i in yield_hashes(g, hashable_nodes)
    ]
    for t in yield_hashable_urls(g, hashable_nodes):
        if (URIRef(t[2].value), None, None) in g:
            continue
        url = merge_get_url(t[2].value, raw="embed")
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(url):
            self.add_error(
                "url", forms.ValidationError(
                    _('Insecure url: %(url)s'),
                    params={"url": url},
                    code="insecure_url"
                )
            )
            return
        try:
            resp = requests.get(url, stream=True, verify=certifi.where())
        except requests.exceptions.ConnectionError:
            raise forms.ValidationError(
                _('invalid url: %(url)s'),
                params={"url": url},
                code="invalid_url"
            )
            return
        if resp.status_code != 200:
            raise forms.ValidationError(
                _("Retrieval failed: %(reason)s"),
                params={"reason": resp.reason},
                code=str(resp.status_code)
            )
            return
        h = get_hashob()
        h.update(XSD.base64Binary.encode("utf8"))
        for chunk in resp.iter_content(BUFFER_SIZE):
            h.update(chunk)
        # do not use add as it could be corrupted by user
        # (user can provide arbitary data)
        g.set((
            URIRef(t[2].value),
            spkcgraph["hash"],
            Literal(h.finalize().hex())
        ))

    # make sure triples are linked to start
    # (user can provide arbitary data)
    g.remove((start, spkcgraph["hashed"], None))
    for t in g.triples((None, spkcgraph["hash"], None)):
        g.add((
            start,
            spkcgraph["hashed"],
            t[0]
        ))
        hashes.append(binascii.unhexlify(t[2].value))

    for i in g.subjects(spkcgraph["type"], Literal("Content")):
        h = get_hashob()
        h.update(i.encode("utf8"))
        hashes.append(h.finalize())
    hashes.sort()

    h = get_hashob()
    for i in hashes:
        h.update(i)
    # do not use add as it could be corrupted by user
    # (user can provide arbitary data)
    digest = h.finalize().hex()
    g.set((
        start,
        spkcgraph["hash"],
        Literal(digest)
    ))
    self.cleaned_data["hash"] = digest
    # replace dvfile by combined file
    self.cleaned_data["dvfile"] = TemporaryUploadedFile(
        "url_uploaded", "text/turtle", None, "utf8"
    )
    g.serialize(
        self.cleaned_data["dvfile"], format="turtle"
    )
    self.cleaned_data["dvfile"].size = \
        self.cleaned_data["dvfile"].tell()
    self.cleaned_data["dvfile"].seek(0, 0)
    # delete graph
    del g
    # make sure, that updated data is used
    self.instance.hash = self.cleaned_data["hash"]
    self.instance.dvfile = self.cleaned_data["dvfile"]
    self.instance.data_type = self.cleaned_data["data_type"]
