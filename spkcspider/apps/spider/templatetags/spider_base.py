from django import template
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def list_own_content(context):
    if context["request"].user.is_authenticated:
        return context["request"].user.usercomponent_set.get(
            name="index"
        ).get_absolute_url()
    return ""


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
