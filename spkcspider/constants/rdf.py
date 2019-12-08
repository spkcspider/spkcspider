"""
    RDF namespaces and related constants
"""

__all__ = [
    "spkcgraph",
]

from rdflib.namespace import Namespace

# Literal allows arbitary datatypes, use this and don't bind
spkcgraph = Namespace("https://spkcspider.net/static/schemes/spkcgraph#")
