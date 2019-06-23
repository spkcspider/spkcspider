__all__ = ["literalize", "uriref", "spkc_namespace"]

from django import template

from rdflib import Literal
from rdflib.namespace import XSD, URIRef
from django.forms import BoundField

from ..constants import spkcgraph
from ..helpers import (
    merge_get_url,
    literalize as _literalize,
    field_to_python as _field_to_python
)

register = template.Library()


@register.filter()
def uriref(path):
    return URIRef(path)


@register.filter()
def is_uriref(value):
    return isinstance(value, URIRef)


@register.filter()
def field_to_python(value):
    return _field_to_python(value)


@register.simple_tag(takes_context=True)
def action_view(context):
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(
        context["hostpart"] + context["request"].path, token=token
    )
    return Literal(url2, datatype=XSD.anyURI)


@register.simple_tag(takes_context=True)
def literalize(
    context, ob, datatype=None, use_uriref=None, domain_base=""
):
    return _literalize(
        ob,
        datatype=datatype, use_uriref=use_uriref,
        domain_base=context["hostpart"]
    )


@register.simple_tag()
def hashable_literalize(field):
    if isinstance(field, BoundField):
        return literalize(getattr(field.field, "hashable", False))
    else:
        return literalize(getattr(field, "hashable", False))


@register.simple_tag()
def spkc_namespace(sub=None):
    if sub:
        return spkcgraph[sub]
    return spkcgraph
