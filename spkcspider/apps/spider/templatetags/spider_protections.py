from django import template
from django.template.loader import render_to_string
from django.utils.translation import gettext as _


register = template.Library()


@register.simple_tag(takes_context=True)
def render_protection(context, protectiontup):
    result, protection = protectiontup
    protection = protection.installed_class
    ctx = {}
    ctx["parent_ctx"] = context
    ctx["data"] = result
    ctx["name"] = _(protection.name)

    if callable(getattr(protection, "render", None)):
        return protection.render(ctx)
    form = getattr(protection, "auth_form", None)
    if form:
        kwargs = {}
        if context["request"].method not in ["GET", "HEAD"]:
            kwargs = {
                'data': context["request"].POST,
                'files': context["request"].FILES,
            }
        ctx["form"] = form(**kwargs)
    template_name = getattr(protection, "template_name")
    if not template_name:
        template_name = "spider_protections/protection_form.html"

    return render_to_string(
        template_name, context=ctx, request=context["request"]
    )


@register.simple_tag(takes_context=True)
def extract_protections(context, extract_name="protections"):
    if hasattr(context.get("request", None), extract_name):
        if getattr(context["request"], extract_name) is not True:
            return getattr(context["request"], extract_name)
    return []
