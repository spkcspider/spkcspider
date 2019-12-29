"""
Does require celery only for async methods
"""
__all__ = {
    "validate", "valid_wait_states", "verify_download_size",
    "async_validate", "verify_tag", "async_verify_tag"
}

import io
import logging
import tempfile

import requests
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from django.conf import settings
from django.core import exceptions
from django.core.files import File
from django.test import Client
from django.utils.translation import gettext as _
from spkcspider import celery_app
from spkcspider.constants.rdf import spkcgraph
from spkcspider.utils.settings import get_settings_func
from spkcspider.utils.urls import merge_get_url

from .conf import get_requests_params
# uses specialized get_hashob from verifier (can be further customized)
from .functions import get_anchor_domain, get_hashob
from .models import DataVerificationTag, VerifySourceObject

logger = logging.getLogger(__name__)


BUFFER_SIZE = 65536  # read in 64kb chunks

valid_wait_states = {
    "RETRIEVING", "HASHING", "STARTED"
}


def verify_download_size(length, current_size=0):
    if not length or not length.isdigit():
        return False
    length = int(length)
    if settings.VERIFIER_MAX_SIZE_ACCEPTED < length:
        return False
    return True


def retrieve_object(obj, current_size, graph=None, session=None):
    # without graph return hash
    ret = None
    try:
        if not isinstance(obj, str):
            if graph is not None:
                graph.parse(obj, format="turtle")
            else:
                h = get_hashob()
                h.update(XSD.base64Binary.encode("utf8"))
                for chunk in iter(lambda: obj.read(BUFFER_SIZE), b''):
                    h.update(chunk)
                return h.finalize()

            return
        # obj is url
        params, inline_domain = get_requests_params(obj)
        if inline_domain:
            resp = Client().get(obj, SERVER_NAME=inline_domain)
            if resp.status_code != 200:
                raise exceptions.ValidationError(
                    _("Retrieval failed: %(reason)s"),
                    params={"reason": resp.reason},
                    code="error_code:{}".format(resp.status_code)
                )

            c_length = resp.get("content-length", None)
            if (
                c_length is None or
                not verify_download_size(c_length, current_size[0])
            ):
                resp.close()
                raise exceptions.ValidationError(
                    _("Content too big or size unset: %(size)s"),
                    params={"size": c_length},
                    code="invalid_size"
                )

            c_length = int(c_length)
            current_size[0] += c_length
            if graph is not None:
                graph.parse(getattr(
                    resp, "streaming_content", io.BytesIO(resp.content)
                ), format="turtle")
            else:
                h = get_hashob()
                h.update(XSD.base64Binary.encode("utf8"))
                for chunk in resp:
                    h.update(chunk)
                ret = h.finalize()
            resp.close()
        else:
            if not session:
                session = requests
            try:
                with session.get(
                    obj, stream=True, **params
                ) as resp:
                    if resp.status_code != 200:
                        raise exceptions.ValidationError(
                            _("Retrieval failed: %(reason)s"),
                            params={"reason": resp.reason},
                            code="error_code:{}".format(resp.status_code)
                        )

                    c_length = resp.headers.get("content-length", None)
                    if (
                        c_length is None or
                        not verify_download_size(c_length, current_size[0])
                    ):
                        raise exceptions.ValidationError(
                            _("Content too big or size unset: %(size)s"),
                            params={"size": c_length},
                            code="invalid_size"
                        )
                    c_length = int(c_length)
                    current_size[0] += c_length
                    if graph is not None:
                        graph.parse(resp.raw, format="turtle")
                    else:
                        h = get_hashob()
                        h.update(XSD.base64Binary.encode("utf8"))
                        for chunk in resp.iter_content(BUFFER_SIZE):
                            h.update(chunk)
                        ret = h.finalize()

            except requests.exceptions.Timeout:
                raise exceptions.ValidationError(
                    _('url timed out: %(url)s'),
                    params={"url": obj},
                    code="timeout_url"
                )
            except requests.exceptions.ConnectionError:
                raise exceptions.ValidationError(
                    _('invalid url: %(url)s'),
                    params={"url": obj},
                    code="invalid_url"
                )
    except Exception:
        logger.error("Parsing graph failed", exc_info=settings.DEBUG)
        raise exceptions.ValidationError(
            _('Invalid graph fromat'),
            code="invalid_format"
        )
    return ret


def validate(ob, hostpart, task=None):
    dvfile = None
    source = None
    g = Graph()
    g.namespace_manager.bind("spkc", spkcgraph, replace=True)
    with requests.session() as session:
        if isinstance(ob, tuple):
            current_size = ob[1]
            with open(ob[0], "rb") as f:
                retrieve_object(f, [current_size], graph=g, session=session)
        else:
            current_size = 0

            source = VerifySourceObject.objects.get(
                id=ob
            )
            url = source.get_url()
            retrieve_object(url, [current_size], graph=g, session=session)

        tmp = list(g.query(
            """
                SELECT ?base ?scope ?pages ?view
                WHERE {
                    ?base spkc:scope ?scope ;
                          spkc:pages.num_pages ?pages ;
                          spkc:pages.current_page ?current_page ;
                          spkc:action:view ?view .
                }
            """,
            initNs={"spkc": spkcgraph},
            initBindings={
                "current_page": Literal(1, datatype=XSD.positiveInteger)
            }
        ))

        if len(tmp) != 1:
            raise exceptions.ValidationError(
                _('Invalid graph'),
                code="invalid_graph"
            )
        tmp = tmp[0]
        start = tmp.base
        # scope = tmp.scope.toPython()
        view_url = tmp.view.toPython()
        pages = tmp.pages.toPython()

        if task:
            task.update_state(
                state='RETRIEVING',
                meta={
                    'page': 1,
                    'num_pages': pages
                }
            )
        if isinstance(ob, tuple):
            split = view_url.split("?", 1)
            source = VerifySourceObject.objects.update_or_create(
                url=split[0], defaults={"get_params": split[1]}
            )

        # retrieve further pages
        for page in range(2, pages+1):
            url = merge_get_url(
                source.get_url(), raw="embed", page=str(page)
            )
            retrieve_object(url, [current_size], graph=g, session=session)

            if task:
                task.update_state(
                    state='RETRIEVING',
                    meta={
                        'page': page,
                        'num_pages': pages
                    }
                )

        # check and clean graph
        data_type = get_settings_func(
            "VERIFIER_CLEAN_GRAPH",
            "spkcspider.apps.verifier.functions.clean_graph"
        )(g, start, source, hostpart)
        if not data_type:
            raise exceptions.ValidationError(
                _('Invalid graph (Verification failed)'),
                code="graph_failed"
            )
        g.remove((None, spkcgraph["csrftoken"], None))

        hashable_nodes = g.query(
            """
                SELECT DISTINCT ?base ?type ?name ?value
                WHERE {
                    ?base spkc:type ?type ;
                          spkc:properties ?prop .
                    ?prop spkc:hashable "true"^^xsd:boolean ;
                          spkc:name ?name ;
                          spkc:value ?value .
                    OPTIONAL {
                        ?value spkc:properties ?prop2 ;
                               spkc:name "info"^^xsd:string ;
                               spkc:value ?info .
                    } .
                }
            """,
            initNs={"spkc": spkcgraph}
        )

        if task:
            task.update_state(
                state='HASHING',
                meta={
                    'hashable_nodes_checked': 0
                }
            )
        # make sure triples are linked to start
        # (user can provide arbitary data)
        g.remove((start, spkcgraph["hashed"], None))
        # MAYBE: think about logic for incoperating hashes
        g.remove((start, spkcgraph["hash"], None))
        nodes = {}
        resources_with_hash = {}
        for count, val in enumerate(hashable_nodes, start=1):
            if isinstance(val.value, URIRef):
                assert(val.info)
                h = get_hashob()
                # should always hash with xsd.string
                h.update(XSD.string.encode("utf8"))
                # don't strip id, as some contents seperate only by id
                h.update(str(val.info).encode("utf8"))
                _hash = h.finalize()
            elif val.value.datatype == spkcgraph["hashableURI"]:
                _hash = resources_with_hash.get(val.value.value)
                if not _hash:
                    url = merge_get_url(val.value.value, raw="embed")
                    if not get_settings_func(
                        "SPIDER_URL_VALIDATOR",
                        "spkcspider.apps.spider.functions.validate_url_default"
                    )(url):
                        raise exceptions.ValidationError(
                            _('invalid url: %(url)s'),
                            params={"url": url},
                            code="invalid_url"
                        )
                    _hash = retrieve_object(
                        url, [current_size], session=session
                    )
                    # do not use add as it could be corrupted by user
                    # (user can provide arbitary data)
                    _uri = URIRef(val.value.value)
                    g.set((
                        _uri,
                        spkcgraph["hash"],
                        Literal(_hash.hex())
                    ))
            else:
                h = get_hashob()
                if val.value.datatype == XSD.base64Binary:
                    h.update(val.value.datatype.encode("utf8"))
                    h.update(val.value.toPython())
                elif val.value.datatype:
                    h.update(val.value.datatype.encode("utf8"))
                    h.update(val.value.encode("utf8"))
                else:
                    h.update(XSD.string.encode("utf8"))
                    h.update(val.value.encode("utf8"))
                _hash = h.finalize()
            h = get_hashob()
            h.update(val.name.toPython().encode("utf8"))
            h.update(_hash)
            base = str(val.base)
            nodes.setdefault(base, ([], val.type))
            nodes[base][0].append(h.finalize())
            if task:
                task.update_state(
                    state='HASHING',
                    meta={
                        'hashable_nodes_checked': count
                    }
                )
    if task:
        task.update_state(
            state='HASHING',
            meta={
                'hashable_nodes_checked': "all"
            }
        )

    # first sort hashes per node and create hash over sorted hashes
    # de-duplicate super-hashes (means: nodes are identical)
    hashes = set()
    for val, _type in nodes.values():
        h = get_hashob()
        for _hob in sorted(val):
            h.update(_hob)
        h.update(_type.encode("utf8"))
        hashes.add(h.finalize())

    # then create hash over sorted de-duplicated node hashes
    h = get_hashob()
    for i in sorted(hashes):
        h.update(i)
    # do not use add as it could be corrupted by user
    # (user can provide arbitary data)
    digest = h.finalize().hex()
    g.set((
        start,
        spkcgraph["hash"],
        Literal(digest)
    ))

    with tempfile.NamedTemporaryFile(delete=True) as dvfile:
        # save in temporary file
        g.serialize(
            dvfile, format="turtle"
        )

        result, created = DataVerificationTag.objects.get_or_create(
            defaults={
                "dvfile": File(dvfile),
                "source": source,
                "data_type": data_type
            },
            hash=digest
        )
    update_fields = set()
    # and source, cannot remove source without replacement
    if not created and source and source != result.source:
        result.source = source
        update_fields.add("source")
    if data_type != result.data_type:
        result.data_type = data_type
        update_fields.add("data_type")
    result.save(update_fields=update_fields)
    verify_tag(result, task=task, ffrom="validate")
    if task:
        task.update_state(
            state='SUCCESS'
        )
    return result


if celery_app:
    @celery_app.task(bind=True, name='async validation')
    def async_validate(self, ob, hostpart):
        ret = validate(ob, hostpart, self)
        return ret.get_absolute_url()
else:
    def async_validate(self, ob, hostpart):
        raise Exception("no celery installed")


def verify_tag(tag, hostpart=None, ffrom="sync_call", task=None):
    """ for auto validation or hooks"""
    if not hostpart:
        hostpart = get_anchor_domain()
    if task:
        task.update_state(
            state='VERIFY'
        )

    if get_settings_func(
        "VERIFIER_TAG_VERIFIER",
        "spkcspider.apps.verifier.functions.verify_tag_default"
    )(tag, hostpart, ffrom):
        try:
            tag.callback(hostpart)
        except exceptions.ValidationError:
            logger.exception("Error while calling back")
    if task:
        task.update_state(
            state='SUCCESS'
        )


if celery_app:
    @celery_app.task(bind=True, name='async verification', ignore_results=True)
    def async_verify_tag(self, tagid, hostpart=None, ffrom="async_call"):
        verify_tag(
            tag=DataVerificationTag.objects.get(id=tagid),
            hostpart=hostpart, task=self, ffrom=ffrom
        )
else:
    def async_verify_tag(self, tagid, hostpart=None, ffrom="async_call"):
        raise Exception("no celery installed")
