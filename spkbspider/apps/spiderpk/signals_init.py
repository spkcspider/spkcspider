from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

from .protections import Protection, installed_protections

@receiver(post_migrate, dispatch_uid="update_protections")
def InitProtectionsCallback(sender, instance, **kwargs):
    for code in installed_protections:
        Protection.objects.get_or_create(code=code)
    temp = Protection.objects.exclude(code__in=installed_protections)
    if temp.exists():
        print("Invalid protections, please update them:", [t.code for t in temp])
