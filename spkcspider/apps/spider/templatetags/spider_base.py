from django import template
from django.urls import reverse
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def list_own_content(context):
    if context["request"].user.is_authenticated:
        return context["request"].user.usercomponent_set.get(
            name="index"
        ).get_absolute_url()
    return ""


@register.simple_tag(takes_context=True)
def list_search_parameters(context):
    ret = set(context["request"].GET.getlist("search"))
    ret.update(context["request"].POST.getlist("search"))
    return ret


@register.simple_tag(takes_context=True)
def update_user_protection(context):
    if context["request"].user.is_authenticated:
        index = context["request"].user.usercomponent_set.get(
            name="index"
        )
        return reverse("spider_base:ucomponent-update", kwargs={
            "name": "index",
            "nonce": index.nonce
        })
    return ""


@register.simple_tag(takes_context=True)
def reverse_get(context, name, **kwargs):
    """ Works only if hostpart and spider_GET is available """
    return "{}{}?{}".format(
        context["hostpart"],
        reverse(name, kwargs=kwargs),
        context["spider_GET"].urlencode()
    )

@register.simple_tag()
def expires_delta(expires):
    return expires-timezone.now()
