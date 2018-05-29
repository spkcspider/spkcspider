__all__ = ("InitProtectionsCallback", "InitUserComponentsCallback")
from django.dispatch import Signal

test_success = Signal(providing_args=["name", "code"])


def InitProtectionsCallback(sender, **kwargs):
    from .protections import initialize_protection_models
    initialize_protection_models()


def InitUserComponentsCallback(sender, instance, **kwargs):
    from .models import UserComponent
    UserComponent.objects.get_or_create(name="index", user=instance)
