__all__ = [
    "paginate_stream", "serialize_stream", "serialize_content",
    "serialize_component"
]


import logging
from urllib.parse import urljoin

from django.http import Http404
from django.core.paginator import InvalidPage, Paginator
from django.utils.translation import gettext as _

from rdflib import URIRef, Literal, XSD


from .constants.static import spkcgraph, VariantType
from .helpers import merge_get_url, add_property


def serialize_content(graph, content, context, embed=False):
    url_content = urljoin(
        context["hostpart"],
        content.get_absolute_url()
    )
    ref_content = URIRef(url_content)
    if (
        context.get("ac_namespace", None) and
        context["sourceref"] != ref_content
    ):
        graph.add((
            context["sourceref"],
            context["ac_namespace"],
            ref_content
        ))

    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_content, token=token)
    if VariantType.feature.value in content.ctype.ctype:
        graph.add((
            ref_content,
            spkcgraph["type"],
            Literal("Feature", datatype=XSD.string)
        ))

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
        Literal("Content", datatype=XSD.string)
    ))
    add_property(
        graph, "info", ref=ref_content, ob=content, datatype=XSD.string
    )
    add_property(
        graph, "priority", ref=ref_content, ob=content
    )
    add_property(
        graph, "id", ref=ref_content, literal=content.get_id(),
        datatype=XSD.integer
    )
    if embed:
        content.content.serialize(graph, ref_content, context)
    return ref_content


def serialize_component(graph, component, context, visible=True):
    url_component = urljoin(
        context["hostpart"],
        component.get_absolute_url()
    )
    ref_component = URIRef(url_component)
    if component.public:
        visible = True
    if not visible and ref_component != context["sourceref"]:
        return None
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(url_component, token=token)
    graph.add((
        ref_component,
        spkcgraph["action:view"],
        URIRef(url2)
    ))
    graph.add((
        ref_component,
        spkcgraph["type"],
        Literal("Component", datatype=XSD.string)
    ))
    if component.primary_anchor:
        url_content = urljoin(
            context["hostpart"],
            component.primary_anchor.get_absolute_url()
        )
        add_property(
            graph, "primary_anchor", ref=ref_component,
            literal=url_content, datatype=XSD.anyURI
        )
    if component.public or context["scope"] == "export":
        add_property(
            graph, "user", ref=ref_component, literal=component.username
        )
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
        graph.add((
            ref_component, spkcgraph["strength"], Literal(component.strength)
        ))
        for feature in component.features.all():
            add_property(
                graph, "features", ref=ref_component,
                literal=feature.name, datatype=XSD.string
            )
    if (
        context.get("uc_namespace", None) and
        context["sourceref"] != ref_component
    ):
        graph.add((
            context["sourceref"],
            context["uc_namespace"],
            ref_component
        ))
    return ref_component


def paginate_stream(query, page_size, limit_depth=None, contentnize=False):
    # WARNING: AssignedContent method doesn't include empty UserComponents
    from .models import AssignedContent
    if contentnize and query.model != AssignedContent:
        query = AssignedContent.objects.filter(
            usercomponent__in=query
        )
    if query.model == AssignedContent:
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
                    logging.warning(
                        "Content references exceeded allowed depth"
                    )
                    break
            else:
                break
        query = query.order_by("usercomponent__id", "id")
    else:
        query = query.order_by("id")
    return Paginator(
        query, page_size, orphans=0, allow_empty_first_page=True
    )


def list_features(graph, component, ref_component, context):
    if not ref_component:
        return
    for feature in component.features.all():
        add_property(
            graph, "features", ref=ref_component,
            literal=feature.name, datatype=XSD.string
        )
        if context["scope"] != "export":
            for url_feature, name in \
                  feature.installed_class.cached_feature_urls():
                url_feature = urljoin(
                    context["hostpart"],
                    url_feature
                )
                ref_feature = URIRef(url_feature)
                graph.add((
                    ref_component,
                    spkcgraph["action:feature"],
                    ref_feature
                ))
                graph.add((
                    ref_feature,
                    spkcgraph["feature:name"],
                    Literal(name, datatype=XSD.string)
                ))


def serialize_stream(
    graph, paginator, context, page=1, embed=False, visible=False
):
    from .models import UserComponent
    if page <= 1:
        graph.add((
            context["sourceref"],
            spkcgraph["pages.num_pages"],
            Literal(paginator.num_pages)
        ))
        graph.add((
            context["sourceref"],
            spkcgraph["pages.size_page"],
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
    if paginator.object_list.model == UserComponent:
        for component in page_view.object_list:
            ref_component = serialize_component(graph, component, context)
            list_features(graph, component, ref_component, context)

    else:
        ref_component = None
        usercomponent = None
        for content in page_view.object_list:
            # leads to possible duplicate usercomponents among multiple pages
            # but every graph is complete
            # and is safer in case a site splits between
            # two different components
            if usercomponent != content.usercomponent:
                usercomponent = content.usercomponent
                ref_component = serialize_component(
                    graph, usercomponent, context,
                    visible=visible
                )
                list_features(graph, usercomponent, ref_component, context)
            ref_content = serialize_content(
                graph, content, context, embed=embed
            )

            if ref_component:
                graph.add((
                    ref_component,
                    spkcgraph["contents"],
                    ref_content
                ))
