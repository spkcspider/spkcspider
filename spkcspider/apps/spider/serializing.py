__all__ = [
    "serialize_content", "serialize_component"
]


import posixpath
from rdflib import URIRef, Literal

from .constants.static import namespaces_spkcspider
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
    namesp = namespaces_spkcspider.content
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url, token=token)
    graph.add(
        (
            content_ref,
            namesp["action/view"],
            URIRef(url2)
        )
    )
    graph.add((content_ref, namesp.id, Literal(content.get_id())))
    graph.add((content_ref, namesp.info, Literal(content.info)))
    content.content.serialize(graph, content_ref, context)
    references = content.references.exclude(
        id__in=graph.objects(predicate=namesp.id)
    )
    for c in references:
        # references field not required, can be calculated
        if (None, namesp.id, Literal(content.get_id())) not in graph:
            serialize_content(graph, c, context)

    return content_ref


def serialize_component(graph, component, context, embed=False):
    url = merge_get_url(
        posixpath.join(
            context["hostpart"],
            component.get_absolute_url()
        ),
        raw=context["request"].GET["raw"]
    )
    namesp = namespaces_spkcspider.usercomponent
    namesp_content = namespaces_spkcspider.content
    comp_ref = URIRef(url)
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url, token=token)
    graph.add(
        (
            comp_ref,
            namesp["action/view"],
            URIRef(url2)
        )
    )
    if component.public or context["scope"] == "export":
        graph.add((comp_ref, namesp.name, Literal(component.__str__())))
        graph.add(
            (comp_ref, namesp.description, Literal(component.description))
        )
    if context["scope"] == "export":
        graph.add(
            (
                comp_ref, namesp.required_passes,
                Literal(component.required_passes)
            )
        )
        graph.add(
            (
                comp_ref, namesp.token_duration,
                Literal(component.token_duration)
            )
        )
    for content in component.contents.all():
        if embed and (
            None, namesp_content.id, Literal(content.get_id())
        ) not in graph:
            ref = serialize_content(graph, content, context)
        else:
            content_url = merge_get_url(
                posixpath.join(
                    context["hostpart"],
                    content.get_absolute_url()
                ),
                raw=context["request"].GET["raw"]
            )
            ref = URIRef(content_url)

        graph.add(
            (
                comp_ref,
                namesp.contents,
                ref
            )
        )
    return comp_ref
