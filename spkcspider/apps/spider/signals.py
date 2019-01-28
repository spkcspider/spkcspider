__all__ = (
    "UpdateSpiderCallback", "InitUserCallback", "UpdateAnchorContent",
    "UpdateAnchorComponent", "update_dynamic", "failed_guess",
    "RemoveTokensLogout", "CleanupCallback",
    "MovePersistentCallback", "move_persistent"
)
from django.dispatch import Signal
from django.contrib.auth import get_user_model
from django.conf import settings
from .constants.static import VariantType
from .helpers import create_b64_id_token
import logging

update_dynamic = Signal(providing_args=[])
move_persistent = Signal(providing_args=["tokens", "to"])
# failed guess of token
failed_guess = Signal(providing_args=["request"])


def TriggerUpdate(sender, **_kwargs):
    results = update_dynamic.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.error(
                "%s failed", receiver, exc_info=result
            )
    logging.info("Update of dynamic content completed")


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
            if (
                instance.ctype and
                VariantType.feature.value in instance.ctype.ctype
            ):
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


def UpdateAnchorContent(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from django.apps import apps
    AuthToken = apps.get_model("spider_base", "AuthToken")
    if instance.primary_anchor_for.exists():
        if "\nanchor\n" not in instance.info:
            # don't call signals, be explicit with bulk=True (default)
            instance.primary_anchor_for.clear(bulk=True)
            # update here
            AuthToken.objects.filter(
                persist=instance.id
            ).update(persist=0)


def UpdateAnchorComponent(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from django.apps import apps
    AuthToken = apps.get_model("spider_base", "AuthToken")
    UserComponent = apps.get_model("spider_base", "UserComponent")
    old = UserComponent.objects.filter(pk=instance.pk).first()
    if old and old.primary_anchor != instance.primary_anchor:
        if instance.primary_anchor:
            persist = 0
            if old.primary_anchor:
                persist = old.primary_anchor.id
            AuthToken.objects.filter(
                persist=persist
            ).update(persist=instance.primary_anchor.id)
        else:
            AuthToken.objects.filter(
                persist=old.primary_anchor.id
            ).update(persist=0)


def MovePersistentCallback(sender, tokens, to, **kwargs):
    from django.apps import apps
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    AssignedContent.objects.filter(
        persist_token__in=tokens
    ).update(usercomponent=to)


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
    UserComponent = apps.get_model("spider_base", "UserComponent")
    for row in AssignedContent.objects.all():
        # works only with django.apps.apps
        row.info = row.content.get_info()
        if not row.token:
            row.token = create_b64_id_token(row.id)
        row.save(update_fields=['info', "token"])

    for row in UserComponent.objects.all():
        if not row.token:
            row.token = create_b64_id_token(row.id)
            row.save(update_fields=["token"])

    for row in get_user_model().objects.prefetch_related(
        "spider_info", "usercomponent_set", "usercomponent_set__contents"
    ).all():
        with transaction.atomic():
            row.spider_info.calculate_allowed_content()
            row.spider_info.calculate_used_space()
            row.spider_info.save()


def InitUserCallback(sender, instance, raw=False, **kwargs):
    if raw:
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
