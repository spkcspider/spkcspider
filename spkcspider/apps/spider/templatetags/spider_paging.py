from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def list_parameters(context, name):
    ret = set(context["request"].GET.getlist(name))
    ret.update(context["request"].POST.getlist(name))
    return ret


@register.simple_tag(takes_context=True)
def get_searchpath(context):
    if "searchpath" in context:
        path = context["searchpath"]
    else:
        path = context["request"].path
    san_get = ""
    if "spider_GET" in context:
        san_get = context["spider_GET"].urlencode()
    return "{}?{}".format(
        path,
        san_get
    )
