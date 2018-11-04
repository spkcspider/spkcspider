__all__ = [
    "paginated_contents", "serialize_stream"
]


import logging
from urllib.parse import urljoin

from django.http import Http404
from django.core.paginator import InvalidPage, Paginator
from django.utils.translation import gettext as _

from rdflib import URIRef, Literal


from .constants.static import namespaces_spkcspider
from .helpers import merge_get_url


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
                namespaces_spkcspider.usercomponent.contents,
                ref_content
            )
        )
    if context.get("ac_namespace", None):
        graph.add((
            context["sourceref"],
            context["ac_namespace"],
            ref_content
        ))

    namesp = namespaces_spkcspider.content
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_content, token=token)
    graph.add(
        (
            ref_content,
            namesp["action/view"],
            URIRef(url2)
        )
    )
    graph.add((ref_content, namesp.id, Literal(content.get_id())))
    graph.add((ref_content, namesp.info, Literal(content.info)))
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
    namesp = namespaces_spkcspider.usercomponent
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_component, token=token)
    graph.add(
        (
            ref_component,
            namesp["action/view"],
            URIRef(url2)
        )
    )
    if component.public or context["scope"] == "export":
        graph.add((ref_component, namesp.name, Literal(component.__str__())))
        graph.add(
            (ref_component, namesp.description, Literal(component.description))
        )
    if context["scope"] == "export":
        graph.add((
            ref_component, namesp.required_passes,
            Literal(component.required_passes)
        ))
        graph.add((
            ref_component, namesp.token_duration,
            Literal(component.token_duration)
        ))
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
            namespaces_spkcspider.meta.pages,
            Literal(paginator.num_pages)
        ))
        graph.add((
            context["sourceref"],
            namespaces_spkcspider.meta.page_size,
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
