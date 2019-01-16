from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def list_parameters(context, name, *args):
    ret = set(context["request"].GET.getlist(name))
    ret.update(context["request"].POST.getlist(name))
    for i in args:
        ret.update(i)
    return ret


@register.simple_tag(takes_context=True)
def get_searchpath(context, page=None, pagename="page"):
    if "searchpath" in context:
        path = context["searchpath"]
    else:
        path = context["request"].path
    san_get = ""
    if "spider_GET" in context:
        san_get = context["spider_GET"].urlencode()
    if page:
        if san_get:
            "{}&{}={}".format(
                san_get,
                pagename,
                page
            )
        else:
            san_get = "{}={}".format(pagename, page)
    if path[-1] == "?":
        return "{}{}".format(
            path,
            san_get
        )
    return "{}?{}".format(
        path,
        san_get
    )
