__all__ = [
    "clean_graph"
]


def clean_graph(mtype, graph):
    if not mtype:
        return None
    elif mtype == "UserComponent":
        return "list"
    elif mtype == "SpiderTag":
        return "layout"
    else:
        return "content"