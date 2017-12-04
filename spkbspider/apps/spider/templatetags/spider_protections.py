from django import template
from django.urls import resolve
from django.core.exceptions import Resolver404, ObjectDoesNotExist

from ..models import AssignedProtection, UserComponent
from ..views import ContentView, ComponentIndex, ContentIndex
from ..protections import installed_protections

register = template.Library()

protected_views = [ContentView, ContentIndex, ComponentIndex]
# includes recovery because recovery should NEVER be included in a normal view query
unavailable_components_for_use = ["recovery", "index"]
unavailable_components_for_list = ["index"]

@register.simple_tag(takes_context=True)
def use_protections(context):
    try:
        res = resolve(context["request"].path)
        if res.func.view_class not in protected_views: return False
        # in case of ComponentIndex None is used so protections work
        # in case of ContentView index is specified so unavailable
        if res.kwargs.get("name", None) in unavailable_components_for_use: return False
        return True
    except Resolver404:
        return False


@register.simple_tag(takes_context=True)
def list_protections(context, path=None):
    if not path:
        path = context["request"].path
    try:
        res = resolve(path)
        if res.kwargs.get("name", None) in unavailable_components_for_list:
            return AssignedProtection.objects.none()
        usercomponent = UserComponent.objects.get(
            user__username=res.kwargs["user"],
            name=res.kwargs.get("name", "index"))
        #.prefetch_related('protection')
        return usercomponent.assigned.filter(protection__code__in=installed_protections)
    except (KeyError, Resolver404, ObjectDoesNotExist):
            return AssignedProtection.objects.none()

# WARNING: check usercomponent user against target
@register.simple_tag
def get_protection(protectionid):
    #.prefetch_related('protection', 'usercomponent')
    # prevent unsafe protections
    ret = AssignedProtection.objects.filter(id=protectionid, protection__code__in=installed_protections)
    return ret.first()
