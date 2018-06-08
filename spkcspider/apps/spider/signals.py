__all__ = (
    "InitProtectionsCallback", "InitUserComponentsCallback",
    "InitContentsCallback"
)
from django.dispatch import Signal

test_success = Signal(providing_args=["name", "code"])


def InitContentsCallback(sender, **kwargs):
    from .contents import initialize_content_models
    initialize_content_models()


def InitProtectionsCallback(sender, **kwargs):
    from .protections import initialize_protection_models
    initialize_protection_models()


def InitUserComponentsCallback(sender, instance, **kwargs):
    from .models import UserComponent, Protection, AssignedProtection
    uc = UserComponent.objects.get_or_create(name="index", user=instance)[0]
    login = Protection.objects.filter(code="login").first()
    if login:
        asuc = AssignedProtection.objects.get_or_create(
            defaults={"active": True},
            usercomponent=uc, protection=login
        )[0]
        if not asuc.active:
            asuc.active = True
            asuc.save()
