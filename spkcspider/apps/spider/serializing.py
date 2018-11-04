__all__ = [
    "paginated_contents", "serialize_stream"
]


import logging
from urllib.parse import urljoin

from django.http import Http404
from django.core.paginator import InvalidPage, Paginator
from django.utils.translation import gettext as _

from rdflib import URIRef, Literal


from .constants.static import spkcgraph
from .helpers import merge_get_url, add_property


def serialize_content(graph, content, context, embed=False):
    url_content = urljoin(
        context["hostpart"],
        content.get_absolute_url()
    )
    ref_content = URIRef(url_content)
    url_component = urljoin(
        context["hostpart"],
        content.usercomponent.get_absolute_url()
    )
    ref_component = URIRef(url_component)
    if (
        context["scope"] == "export" or
        (
            ref_component == context["sourceref"] and
            content.usercomponent.public
        )
    ):
        graph.add(
            (
                ref_component,
                spkcgraph["contents"],
                ref_content
            )
        )
    if context.get("ac_namespace", None):
        graph.add((
            context["sourceref"],
            context["ac_namespace"],
            ref_content
        ))

    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_content, token=token)
    graph.add(
        (
            ref_content,
            spkcgraph["action:view"],
            URIRef(url2)
        )
    )
    graph.add((
        ref_content,
        spkcgraph["type"],
        Literal("Content")
    ))
    add_property(
        graph, "info", ref=ref_content, ob=content
    )
    if embed:
        content.content.serialize(graph, ref_content, context)
    return ref_content


def serialize_component(graph, component, context):
    url_component = urljoin(
        context["hostpart"],
        component.get_absolute_url()
    )
    ref_component = URIRef(url_component)
    if (
        context["scope"] != "export" and
        (
            ref_component != context["sourceref"] or
            not component.public
        )
    ):
        return ref_component
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_component, token=token)
    graph.add(
        (
            ref_component,
            spkcgraph["action:view"],
            URIRef(url2)
        )
    )
    if component.public or context["scope"] == "export":
        add_property(
            graph, "name", ref=ref_component, literal=component.__str__()
        )
        add_property(
            graph, "description", ref=ref_component, ob=component
        )
    if context["scope"] == "export":
        add_property(
            graph, "required_passes", ref=ref_component, ob=component
        )
        add_property(
            graph, "token_duration", ref=ref_component, ob=component
        )
    if context.get("uc_namespace", None):
        graph.add((
            context["sourceref"],
            context["uc_namespace"],
            ref_component
        ))
    return ref_component


def paginated_contents(query, page_size, limit_depth=None):
    from .models import AssignedContent
    length = len(query)
    count = 0
    while True:
        query = query.union(
            AssignedContent.objects.filter(referenced_by__in=query)
        )
        if len(query) != length:
            length = len(query)
            count += 1
            if limit_depth and count > limit_depth:
                logging.warning("Content references exceeded maximal depth")
                break
        else:
            break
    query = query.order_by("usercomponent__id", "id")
    return Paginator(query, page_size, orphans=0, allow_empty_first_page=True)


def serialize_stream(graph, paginator, context, page=1, embed=False):
    if page <= 1:
        graph.add((
            context["sourceref"],
            spkcgraph["pages:num_pages"],
            Literal(paginator.num_pages)
        ))
        graph.add((
            context["sourceref"],
            spkcgraph["pages:size_page"],
            Literal(paginator.per_page)
        ))
    try:
        page_view = paginator.get_page(page)
    except InvalidPage as e:
        exc = Http404(_('Invalid page (%(page_number)s): %(message)s') % {
            'page_number': page,
            'message': str(e)
        })
        logging.exception(exc)
        raise exc
    if page <= 1 or len(page_view.object_list) == 0:
        usercomponent = None
    else:
        usercomponent = page_view.object_list[0].usercomponent
    for content in page_view.object_list:
        if usercomponent != content.usercomponent:
            serialize_component(
                graph, content.usercomponent, context
            )
            usercomponent = content.usercomponent
        serialize_content(
            graph, content, context, embed=embed
        )
