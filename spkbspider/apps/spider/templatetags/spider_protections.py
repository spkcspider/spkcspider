from django import template
from django.template.loader import render_to_string

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

    raise Exception("more render methods are not implemented")
