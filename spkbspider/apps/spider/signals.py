from django.dispatch import Signal

test_success = Signal(providing_args=["name", "code"])

def InitProtectionsCallback(sender, **kwargs):
    from .protections import installed_protections
    from .models import Protection
    for code, val in installed_protections.items():
        ret = Protection.objects.get_or_create(code=code)[0]
        ret.skip_render = val.skip_render
        ret.save()
    temp = Protection.objects.exclude(code__in=installed_protections.keys())
    if temp.exists():
        print("Invalid protections, please update or remove them:", [t.code for t in temp.keys()])
