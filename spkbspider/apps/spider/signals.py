__all__ = ("InitProtectionsCallback", "InitUserComponentsCallback")
from django.dispatch import Signal

test_success = Signal(providing_args=["name", "code"])


def InitProtectionsCallback(sender, **kwargs):
    from .protections import installed_protections
    from .models import Protection
    for code, val in installed_protections.items():
        ret = Protection.objects.get_or_create(
            defaults={"ptype": val.ptype}, code=code
        )[0]
        if ret.ptype != val.ptype:
            ret.ptype = val.ptype
            ret.save()
    temp = Protection.objects.exclude(code__in=installed_protections.keys())
    if temp.exists():
        print("Invalid protections, please update or remove them:",
              [t.code for t in temp])


def InitUserComponentsCallback(sender, instance, **kwargs):
    from .models import UserComponent
    UserComponent.objects.get_or_create(name="index", user=instance)
