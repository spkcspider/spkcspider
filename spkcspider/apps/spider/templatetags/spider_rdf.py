__all__ = ["literalize", "spkc_namespace"]

from django import template
from django.forms import BoundField

from rdflib import Literal
from rdflib.namespace import XSD

from ..constants.static import spkcgraph

register = template.Library()


@register.simple_tag()
def literalize(ob, datatype=None):
    if isinstance(ob, BoundField):
        if not datatype:
            datatype = getattr(ob.field, "spkc_datatype", None)
        ob = ob.data
    if ob is None:
        return Literal("", datatype=datatype, normalize=False)
    if hasattr(ob, "get_absolute_url"):
        if not datatype:
            datatype = XSD.anyURI
        return Literal(ob.get_absolute_url(), datatype=datatype)
    return Literal(ob, datatype=datatype)


@register.simple_tag()
def hashable_literalize(field):
    return literalize(getattr(field, "hashable", False))


@register.simple_tag()
def spkc_namespace(sub=None):
    if sub:
        return spkcgraph[sub]
    return spkcgraph
