__all__ = (
    "UpdateSpiderCb", "InitUserCb", "update_dynamic",
    "DeleteContentCb", "CleanupCb", "MovePersistentCb",
    "move_persistent", "failed_guess",
    "UpdateAnchorContentCb", "UpdateAnchorComponentCb"
)
from django.dispatch import Signal
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db import transaction

from django.apps import apps
from .constants import VariantType
from .helpers import create_b64_id_token
import logging

update_dynamic = Signal(providing_args=[])
move_persistent = Signal(providing_args=["tokens", "to"])
# failed guess of token
failed_guess = Signal(providing_args=["request"])

_empty_set = frozenset()


def TriggerUpdate(sender, **_kwargs):
    results = update_dynamic.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.error(
                "%s failed", receiver, exc_info=result
            )
    logging.info("Update of dynamic content completed")


def DeleteContentCb(sender, instance, **_kwargs):
    # connect if your content object can be deleted without AssignedContent
    ContentType = apps.get_model("contenttypes", "ContentType")
    AssignedContent = apps.get_model("spider_base", "AssignedContent")

    AssignedContent.objects.filter(
        object_id=instance.id,
        content_type=ContentType.objects.get_for_model(sender)
    ).delete()


def CleanupCb(sender, instance, **kwargs):
    stored_exc = None
    if sender._meta.model_name == "usercomponent":
        # if component is deleted the content deletion handler cannot find
        # the user. Here if the user is gone counting doesn't matter anymore
        if instance.user:
            try:
                s = instance.get_accumulated_size()
                # because of F expressions no atomic is required
                instance.user.spider_info.update_with_quota(-s[0], "local")
                instance.user.spider_info.update_with_quota(-s[1], "remote")
                instance.user.spider_info.save(
                    update_fields=["used_space_local", "used_space_remote"]
                )
            except ObjectDoesNotExist:
                pass
            except Exception as exc:
                logging.exception(
                    "update size failed, trigger expensive recalculation",
                    exc_inf=exc
                )
                user = instance.user
                with transaction.atomic():
                    user.spider_info.calculate_allowed_content()
                    user.spider_info.calculate_used_space()
                    user.spider_info.save()

    elif sender._meta.model_name == "assignedcontent":
        if instance.usercomponent and instance.usercomponent.user:
            f = "local"
            if (
                instance.ctype and
                VariantType.component_feature.value in instance.ctype.ctype
            ):
                f = "remote"
            try:
                instance.usercomponent.user.spider_info.update_with_quota(
                    -instance.get_size(), f
                )
                # because of F expressions no atomic is required
                instance.usercomponent.user.spider_info.save(
                    update_fields=["used_space_local", "used_space_remote"]
                )
            except Exception as exc:
                logging.error(
                    "update size failed, trigger expensive recalculation",
                    exc_info=exc
                )
                stored_exc = exc
        if instance.content:
            instance.content.delete(False)
        if stored_exc:
            user = instance.usercomponent.user
            with transaction.atomic():
                user.spider_info.calculate_allowed_content()
                user.spider_info.calculate_used_space()
                user.spider_info.save()


def UpdateAnchorComponentCb(sender, instance, raw=False, **kwargs):
    if raw:
        return
    UserComponent = apps.get_model("spider_base", "UserComponent")
    AuthToken = apps.get_model("spider_base", "AuthToken")
    AssignedContent = apps.get_model("spider_base", "AssignedContent")

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

        if old.primary_anchor:
            old.primary_anchor.referenced_by.clear(
                old.primary_anchor.referenced_by.filter(
                    attached_to_primary_anchor=True
                )
            )
        if instance.primary_anchor:
            instance.primary_anchor.referenced_by.add(
                AssignedContent.objects.filter(
                    usercomponent=instance,
                    attached_to_primary_anchor=True
                )
            )


def UpdateAnchorContentCb(sender, instance, raw=False, **kwargs):
    if raw:
        return
    AuthToken = apps.get_model("spider_base", "AuthToken")
    if (
        instance.primary_anchor_for.exists() and
        "\x1eanchor\x1e" not in instance.info
    ):
        # don't call signals, be explicit with bulk=True (default)
        instance.primary_anchor_for.clear(bulk=True)
        # update here
        AuthToken.objects.filter(
            persist=instance.id
        ).update(persist=0)


def MovePersistentCb(sender, tokens, to, **kwargs):
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    AssignedContent.objects.filter(
        attached_to_token__in=tokens
    ).update(usercomponent=to)


def UpdateSpiderCb(**_kwargs):
    # provided apps argument lacks model function support
    # so use this
    from .contents import initialize_content_models
    from .protections import initialize_protection_models
    initialize_content_models(apps)
    initialize_protection_models(apps)

    # regenerate info field
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    UserComponent = apps.get_model("spider_base", "UserComponent")
    UserComponent.objects.filter(name="index").update(strength=10)
    for row in AssignedContent.objects.all():
        # works only with django.apps.apps
        row.info = row.content.get_info()
        if not row.token:
            row.token = create_b64_id_token(row.id, "_")
        if not row.content.expose_name or not row.name:
            row.name = row.content.get_content_name()
        if not row.content.expose_description:
            row.description = row.content.get_content_description()
        assert(row.description is not None)
        assert(row.name is not None)
        row.save(update_fields=['name', 'description', 'info', "token"])

    for row in UserComponent.objects.all():
        if not row.token:
            row.token = create_b64_id_token(row.id, "_")
            row.save(update_fields=["token"])

    for row in get_user_model().objects.prefetch_related(
        "spider_info", "usercomponent_set", "usercomponent_set__contents"
    ).all():
        with transaction.atomic():
            row.spider_info.calculate_allowed_content()
            row.spider_info.calculate_used_space()
            row.spider_info.save()


def InitUserCb(sender, instance, raw=False, **kwargs):
    if raw:
        return

    Protection = apps.get_model("spider_base", "Protection")
    UserComponent = apps.get_model("spider_base", "UserComponent")
    UserInfo = apps.get_model("spider_base", "UserInfo")

    # overloaded get_or_create calculates strength, ...
    uc = UserComponent.objects.get_or_create(
        defaults={"public": False},
        name="index", user=instance
    )[0]
    login = Protection.objects.filter(code="login").first()
    if login:
        uc.protections.update_or_create(
            defaults={"active": True}, protection=login
        )[0]

    if getattr(settings, "USE_CAPTCHAS", False):
        captcha = Protection.objects.filter(code="captcha").first()
        uc.protections.get_or_create(
            defaults={"active": True}, protection=captcha
        )[0]
    uinfo = UserInfo.objects.get_or_create(
        user=instance
    )[0]
    # save not required, m2m field
    uinfo.calculate_allowed_content()

    if kwargs.get("created", False):
        for name, value in getattr(
            settings, "SPIDER_DEFAULT_COMPONENTS", {}
        ).items():
            # overloaded get_or_create calculates strength, ...
            ob, created = UserComponent.objects.get_or_create(
                defaults={"public": value.get("public", False)},
                name=name, user=instance
            )
            if created:
                for f in value.get("features", _empty_set):
                    feature = uinfo.allowed_content.filter(
                        name=f
                    ).first()
                    if feature:
                        ob.features.add(feature)
