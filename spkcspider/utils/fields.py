__all__ = (
    "literalize", "field_to_python", "add_property", "add_by_field",
    "prepare_description"
)

import re
from urllib.parse import urljoin
from functools import reduce

from django.conf import settings
from django.forms import BoundField, Field
from rdflib import RDF, XSD, BNode, Literal, URIRef
from spkcspider.constants import spkcgraph

# for not spamming sets
_empty_set = frozenset()


def field_to_python(value):
    if isinstance(value, BoundField):
        data = value.initial
        if value.form.is_bound:
            value = value.field.bound_data(value.data, data)
        else:
            value = data
    return value


def literalize(
    ob=None, datatype=None, use_uriref=None, domain_base=""
):
    if isinstance(ob, BoundField):
        if not datatype:
            datatype = getattr(ob.field, "spkc_datatype", None)
        if use_uriref is None:
            use_uriref = getattr(ob.field, "spkc_use_uriref", None)
        ob = field_to_python(ob)
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
            # add raw=embed, download and hash downloaded object
            datatype = spkcgraph["hashableURI"]
        if use_uriref is None:
            use_uriref = True
        ob = ob.get_absolute_url()
    elif isinstance(ob, str) and not datatype:
        datatype = XSD.string
    if use_uriref:
        return URIRef(urljoin(domain_base, ob))
    return Literal(ob, datatype=datatype)


def add_property(
    graph, name, ref=None, ob=None, literal=None, datatype=None,
    iterate=False
):
    value_node = BNode()
    if ref:
        graph.add((
            ref, spkcgraph["properties"],
            value_node
        ))
    graph.add((
        value_node, spkcgraph["name"],
        Literal(name, datatype=XSD.string)
    ))
    if literal is None:
        literal = getattr(ob, name)
    if not iterate:
        literal = [literal]
    for l in literal:
        graph.add((
            value_node, spkcgraph["value"],
            Literal(l, datatype=datatype)
        ))
    if not literal:
        graph.set((value_node, spkcgraph["value"], RDF.nil))
    return value_node


def _field_helper(ob, attr):
    return getattr(ob, attr)


def add_by_field(dic, field="__name__"):
    def _func(klass):
        # should be able to block real object
        if "{}.{}".format(klass.__module__, klass.__qualname__) not in getattr(
            settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
        ):
            dic[reduce(_field_helper, [klass, *field.split(".")])] = klass

        return klass
    return _func


_cleanstr = re.compile(r'<+.*>+')
_whitespsplit = re.compile(r'\s+')


def prepare_description(raw_html, amount=0):
    text = _cleanstr.sub(' ', raw_html).\
        replace("<", " ").replace(">", " ").strip()
    return _whitespsplit.split(text, amount)
