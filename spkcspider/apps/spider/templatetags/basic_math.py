from django import template

register = template.Library()


@register.filter(name='divide')
def divide(value, arg):
    # arg is in string format
    return value // int(arg)


@register.filter(name='remainder')
def remainder(value, arg):
    # arg is in string format
    return value % int(arg)
