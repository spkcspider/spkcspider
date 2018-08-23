__all__ = (
    "UpdateSpiderCallback", "InitUserCallback", "DeleteContentCallback",
    "test_success"
)
from django.dispatch import Signal

from django.conf import settings

test_success = Signal(providing_args=["name", "code"])


def DeleteContentCallback(sender, instance, **kwargs):
    instance.content.delete(False)


def UpdateSpiderCallback(sender, plan=None, **kwargs):
    # provided apps argument lacks model function support
    # so use this
    from django.apps import apps
    from .contents import initialize_content_models
    from .protections import initialize_protection_models
    initialize_content_models(apps)
    initialize_protection_models(apps)

    # regenerate info field
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    UserInfo = apps.get_model("spider_base", "UserInfo")
    for row in AssignedContent.objects.all():
        # works only with django.apps.apps
        row.info = row.content.get_info()
        row.save(update_fields=['info'])

    for row in UserInfo.objects.all():
        row.calculate_allowed_content()


def InitUserCallback(sender, instance, **kwargs):
    from .models import UserComponent, Protection, AssignedProtection, UserInfo

    uc = UserComponent.objects.get_or_create(name="index", user=instance)[0]
    require_save = False
    login = Protection.objects.filter(code="login").first()
    if login:
        asp = AssignedProtection.objects.get_or_create(
            defaults={"active": True},
            usercomponent=uc, protection=login
        )[0]
        if not asp.active:
            asp.active = True
            require_save = True

    if getattr(settings, "USE_CAPTCHAS", False):
        captcha = Protection.objects.filter(code="captcha").first()
        asp = AssignedProtection.objects.get_or_create(
            defaults={"active": True},
            usercomponent=uc, protection=captcha
        )[0]
        if not asp.active:
            asp.active = True
            require_save = True
    uinfo = UserInfo.objects.get_or_create(
        user=instance
    )[0]
    uinfo.calculate_allowed_content()
    if require_save:
        asp.save()
