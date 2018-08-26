from django import template
register = template.Library()


@register.filter(name='divide')
def divide(value, arg):
    return value//int(arg)


@register.filter(name='remainder')
def remainder(value, arg):
    return value % int(arg)
