__all__ = ["literalize", "uriref", "spkc_namespace"]

from django import template
from django.forms import BoundField, Field

from rdflib import Literal
from rdflib.namespace import XSD, RDF, URIRef

from ..constants import spkcgraph
from ..helpers import merge_get_url

register = template.Library()


@register.filter()
def uriref(path):
    return URIRef(path)


@register.filter()
def is_uriref(value):
    return isinstance(value, URIRef)


@register.simple_tag(takes_context=True)
def action_view(context):
    token = getattr(context["request"], "auth_token", None)
    if token:
        token = token.token
    url2 = merge_get_url(
        context["hostpart"] + context["request"].path, token=token
    )
    return Literal(url2, datatype=XSD.anyURI)


@register.simple_tag()
def literalize(ob, datatype=None, use_uriref=None):
    if isinstance(ob, BoundField):
        if not datatype:
            datatype = getattr(ob.field, "spkc_datatype", None)
        if use_uriref is None:
            use_uriref = getattr(ob.field, "spkc_use_uriref", None)
        ob = ob.value()
    elif isinstance(datatype, BoundField):
        if use_uriref is None:
            use_uriref = getattr(datatype.field, "spkc_use_uriref", None)
        datatype = getattr(datatype.field, "spkc_datatype", None)
    elif isinstance(datatype, Field):
        if use_uriref is None:
            use_uriref = getattr(datatype, "spkc_use_uriref", None)
        datatype = getattr(datatype, "spkc_datatype", None)
    if ob is None:
        return RDF.nil
    if hasattr(ob, "get_absolute_url"):
        if not datatype:
            datatype = spkcgraph["hashableURI"]
        if use_uriref is None:
            use_uriref = True
        ob = ob.get_absolute_url()
    elif isinstance(ob, str) and not datatype:
        datatype = XSD.string
    if use_uriref:
        return URIRef(ob)
    return Literal(ob, datatype=datatype)


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
