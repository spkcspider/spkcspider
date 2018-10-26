__all__ = [
    "ns_uc", "ns_ac", "ns_content", "ns_status", "ns_prot", "merge_get_url",
    "serialize_content", "serialize_component"
]


import posixpath
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit

from rdflib import Namespace, Literal, URIRef

ns_uc = Namespace("https:///spkcspider.net/UserComponent")
ns_ac = Namespace("https:///spkcspider.net/AssignedContent")
ns_content = Namespace("https:///spkcspider.net/Content")
ns_status = Namespace("https:///spkcspider.net/Status")
ns_prot = Namespace("https:///spkcspider.net/Protection")


def merge_get_url(url, **kwargs):
    urlparsed = urlsplit(url)
    GET = parse_qs(urlparsed.query)
    GET.update(kwargs)
    return urlunsplit(*urlparsed[:3], urlencode(GET), "")


def serialize_content(graph, content, context):
    url = merge_get_url(
        posixpath.join(
            context["hostpart"],
            content.get_absolute_url()
        ),
        raw=context["request"].GET["raw"]
    )
    content_ref = URIRef(url)
    graph.add((content_ref, ns_ac.info, Literal(content.info)))
    graph.add((content_ref, ns_ac.type, Literal(content.ctype.ctype)))
    content.content.serialize(graph, content_ref, context)
    for c in content.references.all():
        # references field not required, can be calculated
        serialize_content(graph, c, context)

    return content_ref


def serialize_component(graph, component, context):
    url = merge_get_url(
        posixpath.join(
            context["hostpart"],
            component.get_absolute_url()
        ),
        raw=context["request"].GET["raw"]
    )
    comp_ref = URIRef(url)
    if component.public or context["scope"] == "export":
        graph.add((comp_ref, ns_uc.name, Literal(component.name)))
        graph.add(
            (comp_ref, ns_uc.description, Literal(component.description))
        )
    if context["scope"] == "export":
        graph.add(
            (
                comp_ref, ns_uc.required_passes,
                Literal(component.required_passes)
            )
        )
        graph.add(
            (
                comp_ref, ns_uc.token_duration,
                Literal(component.token_duration)
            )
        )
    for content in component.contents.all():
        graph.add(
            (
                comp_ref,
                ns_uc.contents,
                serialize_content(graph, content, context, component)
            )
        )
    return comp_ref
