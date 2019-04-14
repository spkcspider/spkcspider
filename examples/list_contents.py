#!/usr/bin/python3

import re

import sys
from rdflib import Graph, URIRef, Literal

from rdflib.namespace import Namespace


spkcgraph = Namespace("https://spkcspider.net/static/schemes/spkcgraph#")
find_raw_attribute = re.compile(r"\?.*raw=(true|embed).*$")
extract_name = re.compile(r"^name=(.*)$", re.M)
extract_model = re.compile(r"^model=(.*)$", re.M)

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Usage: {} <url>".format(sys.argv[0]))
        exit(0)
    print("Execute:", *sys.argv)

    url = sys.argv[1]
    format = "html"
    if find_raw_attribute.search(url):
        print("Use turtle")
        format = "turtle"
    g = Graph()
    g.bind("spkcspider", spkcgraph)
    g.parse(url, format=format)
    contents = list(
        g.subjects(
            predicate=URIRef(
                'https://spkcspider.net/static/schemes/spkcgraph#type'
                # alternative: use spkcgraph namespace
            ),
            object=Literal(
                'Content',
                datatype=URIRef('http://www.w3.org/2001/XMLSchema#string')
                # alternative: use XSD namespace
            )
        )
    )
    for c in contents:
        info = None
        t = None
        print("Content:")
        print("Type:", g.value(subject=c, predicate=spkcgraph["type"]))
        for p in g.objects(subject=c, predicate=spkcgraph["properties"]):
            name = g.value(subject=p, predicate=spkcgraph["name"])
            if str(name) == "info":
                info = g.value(subject=p, predicate=spkcgraph["value"])
        print("Name (if available):", *extract_name.findall(info))
        print("Model:", *extract_model.findall(info))
        print("Info:", info.replace("\x1e", "|"))
        print()
