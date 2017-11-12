from django.dispatch import Signal
from .models import Protection
from .protections import installed_protections

test_success = Signal(providing_args=["name", "code"])

def InitProtectionsCallback(sender, **kwargs):
    for code in installed_protections:
        Protection.objects.get_or_create(code=code)
    temp = Protection.objects.exclude(code__in=installed_protections)
    if temp.exists():
        print("Invalid protections, please update or remove them:", [t.code for t in temp])
