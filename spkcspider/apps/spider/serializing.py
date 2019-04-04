__all__ = [
    "paginate_stream", "serialize_stream", "serialize_content",
    "serialize_component", "list_features"
]


import logging
from urllib.parse import urljoin

from django.http import Http404
from django.core.paginator import InvalidPage, Paginator
from django.utils.translation import gettext as _
from django.db.models import Q

from rdflib import URIRef, Literal, XSD


from .constants import spkcgraph, VariantType, get_anchor_domain
from .helpers import merge_get_url, add_property


# TODO replace by proper tree search (connect by/recursive query)
def references_q(ids, limit, prefix=""):
    ids = set(ids)
    q = Q()
    for i in range(0, limit+1):
        q |= Q(**{"{}{}id__in".format(prefix, "referenced_by__"*i): ids})
    return q


def list_features(graph, entity, ref_entity, context):
    from .models import UserComponent, ContentVariant
    if not ref_entity:
        return
    if isinstance(entity, UserComponent):
        active_features = entity.features.all()
    else:
        active_features = ContentVariant.objects.filter(
            Q(feature_for_contents=entity) |
            Q(feature_for_components=entity.usercomponent)
        )
    add_property(
        graph, "features", ref=ref_entity,
        literal=active_features.values_list("name", flat=True),
        datatype=XSD.string,
        iterate=True
    )
    for feature in active_features:
        if context["scope"] != "export":
            for url_feature, name in \
                  feature.installed_class.cached_feature_urls():
                url_feature = urljoin(
                    context["hostpart"],
                    url_feature
                )
                ref_feature = URIRef(url_feature)
                graph.add((
                    ref_entity,
                    spkcgraph["action:feature"],
                    ref_feature
                ))
                graph.add((
                    ref_feature,
                    spkcgraph["feature:name"],
                    Literal(name, datatype=XSD.string)
                ))


def serialize_content(graph, content, context, embed=False):
    if VariantType.anchor.value in content.ctype.ctype:
        url_content = urljoin(
            get_anchor_domain(),
            content.get_absolute_url()
        )
    else:
        url_content = urljoin(
            context["hostpart"],
            content.get_absolute_url()
        )
    ref_content = URIRef(url_content)
    # is already node in graph
    if (ref_content, spkcgraph["type"], None) in graph:
        return ref_content
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
    if (
        VariantType.component_feature.value in content.ctype.ctype or
        VariantType.content_feature.value in content.ctype.ctype
    ):
        graph.add((
            ref_content,
            spkcgraph["type"],
            Literal("Feature", datatype=XSD.string)
        ))
    else:
        graph.add((
            ref_content,
            spkcgraph["type"],
            Literal("Content", datatype=XSD.string)
        ))

    graph.set(
        (
            ref_content,
            spkcgraph["action:view"],
            URIRef(url2)
        )
    )
    add_property(
        graph, "info", ref=ref_content, ob=content, datatype=XSD.string
    )
    add_property(
        graph, "priority", ref=ref_content, ob=content
    )
    add_property(
        graph, "id", ref=ref_content, literal=content.id,
        datatype=XSD.integer
    )
    if context["scope"] == "export":
        add_property(
            graph, "attached_to_content", ref=ref_content, ob=content
        )

    if embed:
        list_features(graph, content, ref_content, context)
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
        add_property(
            graph, "features", ref=ref_component,
            literal=component.features.values_list("name", flat=True),
            datatype=XSD.string, iterate=True
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
        query = AssignedContent.objects.filter(
            references_q(
                query.values_list("id", flat=True),
                limit_depth or 30
            )
        )
        query = query.order_by("usercomponent__id", "id")
    else:
        query = query.order_by("id")
    return Paginator(
        query, page_size, orphans=0, allow_empty_first_page=True
    )


def serialize_stream(
    graph, paginator, context, page=1, embed=False, visible=False
):
    from .models import UserComponent
    if page <= 1:
        graph.add((
            context["sourceref"],
            spkcgraph["pages.num_pages"],
            Literal(paginator.num_pages, datatype=XSD.positiveInteger)
        ))
        graph.add((
            context["sourceref"],
            spkcgraph["pages.size_page"],
            Literal(paginator.per_page, datatype=XSD.positiveInteger)
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

    graph.add((
        context["sourceref"],
        spkcgraph["pages.current_page"],
        Literal(page_view.number, datatype=XSD.positiveInteger)
    ))
    if paginator.object_list.model == UserComponent:
        for component in page_view.object_list:
            ref_component = serialize_component(graph, component, context)
            list_features(graph, component, ref_component, context)

    else:
        # either start with invalid usercomponent which will be replaced
        #  or use bottom-1 usercomponent to detect split
        if page <= 1:
            usercomponent = None
            ref_component = None
        else:
            _pos = ((page - 1) * paginator.per_page) - 1
            usercomponent = paginator.object_list[_pos]
            ref_component = URIRef(urljoin(
                context["hostpart"],
                usercomponent.get_absolute_url()
            ))
        for content in page_view.object_list:
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
