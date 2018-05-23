from django import template
from django.template.loader import render_to_string

from .models import AssignedProtection, Protection, UserComponent
from ..protections import installed_protections

register = template.Library()


@register.simple_tag(takes_context=True)
def render_protection(context, protection):

    if callable(getattr(protection, "render", None)):
        return protection.render(context)

    if getattr(protection, "template_name", None):
        return render_to_string(protection.template_name, context)

    if getattr(protection, "form", None):
        ctx = context.copy()
        ctx["form"] = protection.form
        return render_to_string("spiderprotections/protection_form.html", ctx)

    if callable(getattr(protection, "__html__", None)):
        return protection.__html__()

    raise Exception("more render methods are not implemented")


@register.simple_tag(takes_context=True)
def render_protections(context, ptype, scope):
    assert("request" in context)
    ret = []
    for p in Protection.filter(ptype=ptype):
        ret.append(
            installed_protections[p.code].authenticate(
                request=context["request"], user=None,
                data={}, obj=p, scope=scope
            )
        )


@register.simple_tag(takes_context=True)
def extract_protections(context, extract_name="auth_results"):
    if hasattr(context.get("request", None), extract_name):
        return getattr(context["request"], extract_name)
