__all__ = [
    "serialize_content", "serialize_component"
]


import posixpath
from rdflib import URIRef, Literal

from .constants.static import namespace_spkcspider
from .helpers import merge_get_url


def serialize_content(graph, content, context):
    url = merge_get_url(
        posixpath.join(
            context["hostpart"],
            content.get_absolute_url()
        ),
        raw=context["request"].GET["raw"]
    )
    content_ref = URIRef(url)
    ns = namespace_spkcspider.assignedcontent
    graph.add((content_ref, ns.info, Literal(content.info)))
    graph.add((content_ref, ns.type, Literal(content.ctype.ctype)))
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
    ns = namespace_spkcspider.usercomponent
    comp_ref = URIRef(url)
    if component.public or context["scope"] == "export":
        graph.add((comp_ref, ns.name, Literal(component.name)))
        graph.add(
            (comp_ref, ns.description, Literal(component.description))
        )
    if context["scope"] == "export":
        graph.add(
            (
                comp_ref, ns.required_passes,
                Literal(component.required_passes)
            )
        )
        graph.add(
            (
                comp_ref, ns.token_duration,
                Literal(component.token_duration)
            )
        )
    for content in component.contents.all():
        graph.add(
            (
                comp_ref,
                ns.contents,
                serialize_content(graph, content, context, component)
            )
        )
    return comp_ref
