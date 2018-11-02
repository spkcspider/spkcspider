__all__ = (
    "UpdateSpiderCallback", "InitUserCallback", "DeleteContentCallback",
    "update_dynamic", "failed_guess", "RemoveTokensLogout"
)
from django.dispatch import Signal
from django.conf import settings
import logging

update_dynamic = Signal(providing_args=[])
# failed guess of combination from id, nonce
failed_guess = Signal(providing_args=[])


def TriggerUpdate(sender, **_kwargs):
    results = update_dynamic.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.exception(result)


def DeleteContentCallback(sender, instance, **kwargs):
    if instance.fake_id is None:
        instance.content.delete(False)
    # because Operations are done on the real object
    # deletions in fake view work too


def UpdateSpiderCallback(**_kwargs):
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
    if kwargs.get("raw", False):
        return
    from .models import UserComponent, Protection, AssignedProtection, UserInfo

    uc = UserComponent.objects.get_or_create_component(
        defaults={"strength": 10},
        name="index", user=instance
    )[0]
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
    if require_save:
        asp.save()
    uinfo = UserInfo.objects.get_or_create(
        user=instance
    )[0]
    # save not required, m2m field
    uinfo.calculate_allowed_content()


def RemoveTokensLogout(sender, user, request, **kwargs):
    from .models import AuthToken
    AuthToken.objects.filter(
        created_by_special_user=user,
        session_key=request.session.session_key
    ).delete()
