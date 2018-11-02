from django import template

from rdflib import BNode

from ..constants.static import namespaces_spkcspider

register = template.Library()


@register.simple_tag()
def bnode():
    return BNode()


@register.simple_tag()
def namespace(ob, sub=None):
    if isinstance(ob, str):
        nname = ob
    else:
        nname = ob._meta.model_name

    ret = getattr(namespaces_spkcspider, nname)
    if sub:
        ret = ret[sub]
    return ret
