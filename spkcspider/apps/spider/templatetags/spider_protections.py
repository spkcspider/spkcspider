from django import template
from django.template.loader import render_to_string


register = template.Library()


@register.simple_tag(takes_context=True)
def render_protection(context, protectiontup):
    result, protection = protectiontup
    ctx = context.copy()
    ctx["data"] = result
    ctx["name"] = protection.name
    ctx["form"] = getattr(protection, "form", None)

    if callable(getattr(protection, "render", None)):
        return protection.render(ctx)

    return render_to_string(
        getattr(
            protection, "template_name",
            "spiderprotections/protection_form.html"
        ), ctx
    )


@register.simple_tag(takes_context=True)
def extract_protections(context, extract_name="protections"):
    if hasattr(context.get("request", None), extract_name):
        if getattr(context["request"], extract_name) is not True:
            return getattr(context["request"], extract_name)
    return []
