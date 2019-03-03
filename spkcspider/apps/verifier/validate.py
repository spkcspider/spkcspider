__all__ = ("validate", "verify_download_size")

import logging
import binascii
import tempfile
import os

from django.utils.translation import gettext_lazy as _
from django.core.files import File
from django.conf import settings
from django.core import exceptions

from rdflib import Graph, URIRef, Literal
from rdflib.namespace import XSD
import requests
import certifi

from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.helpers import merge_get_url, get_settings_func

from .constants import BUFFER_SIZE
from .functions import get_hashob
from .models import VerifySourceObject, DataVerificationTag

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


def validate(ob, task=None):
    dvfile = None
    source = None
    if isinstance(ob, tuple):
        dvfile = open(ob[0], "r+b")
        current_size = ob[1]
    else:
        current_size = 0
        dvfile = tempfile.NamedTemporaryFile(delete=False)

        source = VerifySourceObject.objects.get(
            id=ob
        )
        url = source.get_absolute_url()

        try:
            resp = requests.get(url, stream=True, verify=certifi.where())
        except requests.exceptions.ConnectionError:
            raise exceptions.ValidationError(
                _('invalid url: %(url)s'),
                params={"url": url},
                code="invalid_url"
            )
        if resp.status_code != 200:
            raise exceptions.ValidationError(
                _("Retrieval failed: %(reason)s"),
                params={"reason": resp.reason},
                code="error_code:{}".format(resp.status_code)
            )

        c_length = resp.headers.get("content-length", None)
        if not verify_download_size(c_length, current_size):
            raise exceptions.ValidationError(
                _("Content too big: %(size)s"),
                params={"size": c_length},
                code="invalid_size"
            )
        c_length = int(c_length)
        current_size += c_length
        # preallocate file
        dvfile.truncate(c_length)
        dvfile.seek(0, 0)

        for chunk in resp.iter_content(BUFFER_SIZE):
            dvfile.write(chunk)
        dvfile.seek(0, 0)
    g = Graph()
    g.namespace_manager.bind("spkc", spkcgraph, replace=True)
    try:
        g.parse(
            dvfile.name,
            format="turtle"
        )
    except Exception as exc:
        if settings.DEBUG:
            dvfile.seek(0, 0)
            logging.error(dvfile.read())
        logging.exception(exc)
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Invalid graph fromat'),
            code="invalid_format"
        )

    tmp = list(g.triples((None, spkcgraph["scope"], None)))
    if len(tmp) != 1:
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Invalid graph'),
            code="invalid_graph"
        )
    start = tmp[0][0]
    scope = tmp[0][2].toPython()
    tmp = list(g.triples((start, spkcgraph["pages.num_pages"], None)))
    if len(tmp) != 1:
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Invalid graph'),
            code="invalid_graph"
        )
    pages = tmp[0][2].toPython()
    tmp = list(g.triples((
        start,
        spkcgraph["pages.current_page"],
        Literal(1, datatype=XSD.positiveInteger)
    )))
    if len(tmp) != 1:
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Must be page 1'),
            code="invalid_page"
        )
    if task:
        task.update_state(
            state='RETRIEVING',
            meta={
                'page': 1,
                'num_pages': pages
            }
        )
    view_url = None
    tmp = list(g.triples((start, spkcgraph["action:view"], None)))
    if len(tmp) != 1:
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Invalid graph'),
            code="invalid_graph"
        )
    view_url = tmp[0][2].toPython()
    if isinstance(ob, tuple):
        split = view_url.split("?", 1)
        source = VerifySourceObject.objects.update_or_create(
            url=split[0], defaults={"get_params": split[1]}
        )
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
        dvfile.close()
        os.unlink(dvfile.name)
        raise exceptions.ValidationError(
            _('Invalid graph type: %(type)s'),
            params={"type": data_type},
            code="invalid_type"
        )

    # retrieve further pages
    for page in range(2, pages+1):
        url = merge_get_url(view_url, raw="embed", page=str(page))
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(url):
            dvfile.close()
            os.unlink(dvfile.name)
            raise exceptions.ValidationError(
                _('Insecure url: %(url)s'),
                params={"url": url},
                code="insecure_url"
            )

        try:
            resp = requests.get(url, stream=True, verify=certifi.where())
        except requests.exceptions.ConnectionError:
            dvfile.close()
            os.unlink(dvfile.name)
            raise exceptions.ValidationError(
                _('Invalid url: %(url)s'),
                params={"url": url},
                code="innvalid_url"
            )
        if resp.status_code != 200:
            dvfile.close()
            os.unlink(dvfile.name)
            raise exceptions.ValidationError(
                _("Retrieval failed: %(reason)s"),
                params={"reason": resp.reason},
                code="error_code:{}".format(resp.status_code)
            )

        c_length = resp.headers.get("content-length", None)
        if not verify_download_size(c_length, current_size):
            dvfile.close()
            os.unlink(dvfile.name)
            raise exceptions.ValidationError(
                _("Content too big: %(size)s"),
                params={"size": c_length},
                code="invalid_size"
            )
        c_length = int(c_length)
        current_size += c_length
        # clear file
        dvfile.truncate(c_length)
        dvfile.seek(0, 0)

        for chunk in resp.iter_content(BUFFER_SIZE):
            dvfile.write(chunk)
        dvfile.seek(0, 0)
        try:
            g.parse(
                dvfile.name,
                format="turtle"
            )
        except Exception as exc:
            if settings.DEBUG:
                dvfile.seek(0, 0)
                logging.error(dvfile.read())
            logging.exception(exc)
            dvfile.close()
            os.unlink(dvfile.name)
            # pages could have changed, but still incorrect
            raise exceptions.ValidationError(
                _("%(page)s is not a \"%(format)s\" file"),
                params={"format": "turtle", "page": page},
                code="invalid_file"
            )

        if task:
            task.update_state(
                state='RETRIEVING',
                meta={
                    'page': page,
                    'num_pages': pages
                }
            )

    hashable_nodes = set(g.subjects(
        predicate=spkcgraph["hashable"], object=Literal(True)
    ))

    hashes = [
        i for i in yield_hashes(g, hashable_nodes)
    ]
    if task:
        task.update_state(
            state='RETRIEVING',
            meta={
                'hashable_urls_checked': 0
            }
        )
    for count, t in enumerate(yield_hashable_urls(g, hashable_nodes), start=1):
        if (URIRef(t[2].value), None, None) in g:
            continue
        url = merge_get_url(t[2].value, raw="embed")
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(url):
            dvfile.close()
            os.unlink(dvfile.name)
            raise exceptions.ValidationError(
                _('Insecure url: %(url)s'),
                params={"url": url},
                code="insecure_url"
            )

        try:
            resp = requests.get(url, stream=True, verify=certifi.where())
        except requests.exceptions.ConnectionError:
            raise exceptions.ValidationError(
                _('Invalid url: %(url)s'),
                params={"url": url},
                code="innvalid_url"
            )
        if resp.status_code != 200:
            raise exceptions.ValidationError(
                _("Retrieval failed: %(reason)s"),
                params={"reason": resp.reason},
                code="code_{}".format(resp.status_code)
            )

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
        if task:
            task.update_state(
                state='RETRIEVING',
                meta={
                    'hashable_urls_checked': count
                }
            )
    if task:
        task.update_state(
            state='HASHING',
        )

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

    dvfile.truncate(0)
    dvfile.seek(0, 0)
    # save in temporary file
    g.serialize(
        dvfile, format="turtle"
    )

    result, created = DataVerificationTag.objects.get_or_create(
        defaults={
            "dvfile": File(dvfile),
            "source": source
        },
        hash=digest
    )
    dvfile.close()
    os.unlink(dvfile.name)
    if not created and source and source != result.source:
        result.source = source
        result.save(update_fields=["source"])
    if task:
        task.update_state(
            state='SUCCESS'
        )
    return result
