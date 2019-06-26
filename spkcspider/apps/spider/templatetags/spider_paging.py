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
    search_get = ""
    if "sanitized_GET" in context:
        search_get = context["sanitized_GET"]
    if page:
        search_get = "{}{}={}&".format(
            search_get, pagename, page
        )
    return "{}?{}".format(
        path.rstrip("?&"),
        search_get
    )
