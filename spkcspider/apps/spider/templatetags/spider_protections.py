from django import template
from django import forms
from django.template.loader import render_to_string


register = template.Library()


@register.simple_tag(takes_context=True)
def render_protection(context, protectiontup):
    result, protection = protectiontup
    protection = protection.installed_class
    ctx = {}
    ctx["parent_ctx"] = context
    ctx["data"] = result
    ctx["protection"] = protection

    if callable(getattr(protection, "render", None)):
        return protection.render(ctx)
    if isinstance(ctx["data"], forms.Form):
        ctx["form"] = ctx["data"]
    elif hasattr(protection, "auth_form"):
        ctx["form"] = protection.auth_form(**ctx["data"])
    template_name = getattr(protection, "template_name")
    if not template_name:
        template_name = "spider_base/protections/protection_form.html"

    return render_to_string(
        template_name, context=ctx, request=context["request"]
    )


@register.simple_tag(takes_context=True)
def extract_protections(context, extract_name="protections"):
    if hasattr(context.get("request", None), extract_name):
        if getattr(context["request"], extract_name) is not True:
            return getattr(context["request"], extract_name)
    return []
