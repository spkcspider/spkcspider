__all__ = (
    "UpdateSpiderCallback", "InitUserCallback",
    "update_dynamic", "failed_guess", "RemoveTokensLogout", "CleanupCallback"
)
from django.dispatch import Signal
from django.contrib.auth import get_user_model
from django.conf import settings
from .constants.static import VariantType
import logging

update_dynamic = Signal(providing_args=[])
# failed guess of combination from id, nonce
failed_guess = Signal(providing_args=[])


def TriggerUpdate(sender, **_kwargs):
    results = update_dynamic.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.error(
                "%s failed", receiver, exc_info=result
            )


def CleanupCallback(sender, instance, **kwargs):
    if sender._meta.model_name == "usercomponent":
        # if component is deleted the content deletion handler cannot find
        # the user. Here if the user is gone counting doesn't matter anymore
        if instance.user and instance.user.spider_info:
            s = instance.get_size()
            # because of F expressions no atomic is required
            instance.user.spider_info.update_with_quota(-s[0], "local")
            instance.user.spider_info.update_with_quota(-s[1], "remote")
            instance.user.spider_info.save(
                update_fields=["used_space_local", "used_space_remote"]
            )
    elif sender._meta.model_name == "assignedcontent":
        if instance.usercomponent and instance.usercomponent.user:
            f = "local"
            if VariantType.feature.value in instance.ctype.ctype:
                f = "remote"
            instance.usercomponent.user.spider_info.update_with_quota(
                -instance.get_size(), f
            )
            # because of F expressions no atomic is required
            instance.usercomponent.user.spider_info.save(
                update_fields=["used_space_local", "used_space_remote"]
            )
        if instance.fake_id is None and instance.content:
            instance.content.delete(False)


def UpdateSpiderCallback(**_kwargs):
    # provided apps argument lacks model function support
    # so use this
    from django.apps import apps
    from django.db import transaction
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
        with transaction.atomic():
            row.spider_info.calculate_allowed_content()
            row.spider_info.calculate_used_space()
            row.spider_info.save()


def InitUserCallback(sender, instance, **kwargs):
    if kwargs.get("raw", False):
        return
    from .models import UserComponent, Protection, UserInfo

    # overloaded get_or_create calculates strength, ...
    uc = UserComponent.objects.get_or_create(
        defaults={"public": False},
        name="index", user=instance
    )[0]
    if kwargs.get("created", False):
        for name, is_public in getattr(
            settings, "DEFAULT_USERCOMPONENTS", {}
        ).items():
            # overloaded get_or_create calculates strength, ...
            UserComponent.objects.get_or_create(
                defaults={"public": is_public},
                name=name, user=instance
            )
    login = Protection.objects.filter(code="login").first()
    if login:
        uc.protections.update_or_create(
            defaults={"active": True}, protection=login
        )[0]

    if getattr(settings, "USE_CAPTCHAS", False):
        captcha = Protection.objects.filter(code="captcha").first()
        uc.protections.update_or_create(
            defaults={"active": True}, protection=captcha
        )[0]
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
