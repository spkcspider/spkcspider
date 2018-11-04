__all__ = (
    "UpdateSpiderCallback", "InitUserCallback",
    "update_dynamic", "failed_guess", "RemoveTokensLogout", "CleanupCallback"
)
from django.dispatch import Signal
from django.contrib.auth import get_user_model
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


def CleanupCallback(sender, instance, **kwargs):
    if sender._meta.model_name == "usercomponent":
        if instance.user:
            instance.user.spider_info.update_quota(-instance.get_size())
    elif sender._meta.model_name == "assignedcontent":
        if instance.usercomponent and instance.usercomponent.user:
            instance.usercomponent.user.spider_info.update_quota(
                -instance.get_size()
            )
        if instance.fake_id is None:
            instance.content.delete(False)


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
    for row in AssignedContent.objects.all():
        # works only with django.apps.apps
        row.info = row.content.get_info()
        row.save(update_fields=['info'])

    for row in get_user_model().objects.prefetch_related(
        "spider_info", "usercomponent_set", "usercomponent_set__contents"
    ).all():
        row.spider_info.calculate_allowed_content()
        row.spider_info.update_used_space()


def InitUserCallback(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    from .models import UserComponent, Protection, AssignedProtection, UserInfo

    uc = UserComponent.objects.get_or_create_component(
        defaults={"strength": 10, "public": False},
        name="index", user=instance
    )[0]
    if kwargs.get("created", False):
        for name, is_public in getattr(
            settings, "DEFAULT_USERCOMPONENTS", {}
        ).items():
            strength = 0 if is_public else 5
            UserComponent.objects.get_or_create_component(
                defaults={"strength": strength, "public": is_public},
                name=name, user=instance
            )
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
