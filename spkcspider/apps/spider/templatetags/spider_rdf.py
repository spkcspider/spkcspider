from django import template

from rdflib import BNode

from ..constants.static import spkcgraph

register = template.Library()


@register.simple_tag()
def bnode(ob=None):
    if ob:
        return BNode(ob.pk)
    return BNode()


@register.simple_tag()
def namespace(sub=None):
    if sub:
        return spkcgraph[sub]
    return spkcgraph
