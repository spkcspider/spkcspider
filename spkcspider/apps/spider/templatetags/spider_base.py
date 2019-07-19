from django import template
from django.urls import reverse
from django.utils import timezone
from django.urls.exceptions import NoReverseMatch

register = template.Library()


@register.filter()
def is_not_or_space(value):
    if not value:
        return True
    return isinstance(value, str) and value.isspace()


@register.simple_tag(takes_context=True)
def shall_show_content(context, content, priority=0):
    return (
        not content.is_hidden or
        (context["request"].is_owner and content.priority > priority) or
        "_unlisted" in context["request"].GET.getlist("search") or
        "_unlisted" in context["request"].POST.getlist("search")
    )


@register.simple_tag(takes_context=True)
def themed_media(context):
    # TODO: implement, just stub
    # uc = context.get("source", context["uc"])
    # media = uc.theme.replace(context.get("media"))
    return context.get("media")


@register.simple_tag(takes_context=True)
def current_url(context):
    try:
        return reverse(
            "{}:{}".format(
                context["request"].resolver_match.namespace,
                context["request"].resolver_match.url_name,
            ),
            args=context["request"].resolver_match.args,
            kwargs=context["request"].resolver_match.kwargs
        )
    except NoReverseMatch:
        return reverse(
            context["request"].resolver_match.url_name,
            args=context["request"].resolver_match.args,
            kwargs=context["request"].resolver_match.kwargs
        )


@register.simple_tag(takes_context=True)
def list_own_content(context):
    ucname = "index"
    if context["request"].user.is_authenticated:
        return context["request"].user.usercomponent_set.get(
            name=ucname
        ).get_absolute_url()
    return ""


@register.simple_tag(takes_context=True)
def update_component(context, name):
    if context["request"].user.is_authenticated:
        uc = context["request"].user.usercomponent_set.only("token").get(
            name=name
        )
        return reverse("spider_base:ucomponent-update", kwargs={
            "token": uc.token
        })
    return ""


@register.simple_tag(takes_context=True)
def reverse_get(context, name, **kwargs):
    """ Works only if hostpart and sanitized_GET is available """
    return "{}{}?{}".format(
        context["hostpart"],
        reverse(name, kwargs=kwargs),
        context["sanitized_GET"]
    )


@register.simple_tag()
def concat_string(*args):
    return "".join(args)


@register.simple_tag()
def expires_delta(expires):
    return expires-timezone.now()


@register.simple_tag()
def token_expires(usercomponent, token):
    return token.created + usercomponent.token_duration


@register.simple_tag(takes_context=True)
def active_feature_names(context):
    return context["active_features"].values_list("name", flat=True)
