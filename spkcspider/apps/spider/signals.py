__all__ = (
    "UpdateSpiderCb", "InitUserCb", "update_dynamic",
    "DeleteContentCb", "CleanupCb", "failed_guess",
    "UpdateContentCb", "UpdateAnchorComponentCb",
    "FeaturesCb", "DeleteFilesCb"
)
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.dispatch import Signal
from spkcspider.constants import ProtectionStateType, VariantType
from spkcspider.utils.security import create_b64_id_token
from . import registry

logger = logging.getLogger(__name__)

update_dynamic = Signal(providing_args=[])
# failed guess of token
failed_guess = Signal(providing_args=["request"])

_empty_set = frozenset()
_feature_update_actions = frozenset({
    "init", "post_add", "post_remove", "post_clear"
})

_ignored_features_for_update = frozenset({
    "DefaultActions", "DomainMode"
})


def TriggerUpdate(sender, **_kwargs):
    results = update_dynamic.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logger.error(
                "%s failed", receiver, exc_info=result
            )
    logger.info("Update of dynamic content completed")


def DeleteContentCb(sender, instance, **_kwargs):
    """
        Connect if content can be deleted without AssignedContent
        beeing deleted.
    """
    instance.associated.delete()


def CleanupCb(sender, instance, **kwargs):
    stored_exc = None
    ContentVariant = apps.get_model("spider_base", "ContentVariant")
    if sender._meta.model_name == "usercomponent":
        # if component is deleted the content deletion handler cannot find
        # the user. Here if the user is gone counting doesn't matter anymore
        if instance.user:
            try:
                # whole component is deleted
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
                logger.exception(
                    "update size failed, trigger expensive recalculation",
                    exc_inf=exc
                )
            user = instance.user

    elif sender._meta.model_name == "assignedcontent":
        if instance.usercomponent and instance.usercomponent.user:
            f = "local"
            if (
                instance.ctype and instance.ctype.is_feature
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
            except ObjectDoesNotExist:
                pass
            except Exception as exc:
                logger.error(
                    "update size failed, trigger expensive recalculation",
                    exc_info=exc
                )
                stored_exc = exc
        if VariantType.feature_connect in instance.ctype.ctype:
            if VariantType.component_feature in instance.ctype.ctype:
                if not instance.usercomponent.contents.filter(
                    ctype=instance.ctype
                ).exclude(id=instance.id):
                    instance.usercomponent.features.remove(instance.ctype)

        if not instance.usercomponent.contents.filter(
            ctype__ctype__contains=VariantType.domain_mode
        ).exclude(id=instance.id):
            instance.usercomponent.features.remove(ContentVariant.objects.get(
                name="DomainMode"
            ))
        # Persistence must not be autoremoved
        user = instance.usercomponent.user

    # expensive path
    if stored_exc:
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
                persist = old.primary_anchor_id
            AuthToken.objects.filter(
                persist=persist
            ).update(persist=instance.primary_anchor_id)
            instance.primary_anchor.referenced_by.add(
                AssignedContent.objects.filter(
                    usercomponent=instance,
                    attached_to_primary_anchor=True
                )
            )
        elif old.primary_anchor:
            AuthToken.objects.filter(
                persist=old.primary_anchor_id
            ).update(persist=0)

            old.primary_anchor.referenced_by.clear(
                old.primary_anchor.referenced_by.filter(
                    attached_to_primary_anchor=True
                )
            )


def UpdateContentCb(sender, instance, raw=False, **kwargs):
    if raw:
        return
    AuthToken = apps.get_model("spider_base", "AuthToken")
    ContentVariant = apps.get_model("spider_base", "ContentVariant")
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

    # check if self depends on DomainMode
    if (
        VariantType.domain_mode in instance.ctype.ctype or
        instance.features.filter(
            ctype__contains=VariantType.domain_mode
        )
    ):
        if not instance.features.filter(name="DomainMode"):
            instance.features.add(ContentVariant.objects.get(
                name="DomainMode"
            ))
    elif instance.features.filter(name="DomainMode"):
        instance.features.remove(ContentVariant.objects.get(
            name="DomainMode"
        ))
    # check if self depends on persist
    if (
        VariantType.persist in instance.ctype.ctype or
        instance.features.filter(
            ctype__contains=VariantType.persist
        )
    ):
        if not instance.usercomponent.features.filter(name="Persistence"):
            instance.usercomponent.features.add(ContentVariant.objects.get(
                name="Persistence"
            ))

    # auto add self as feature
    if (
        VariantType.component_feature in instance.ctype.ctype and
        VariantType.feature_connect in instance.ctype.ctype
    ):
        instance.usercomponent.features.add(instance.ctype)


def FeaturesCb(
    sender, instance, pk_set=(), model=None,
    action="_update", raw=False, created=False, **kwargs
):
    """
        used for:
        Content & Component update: action="_update", raw, created
        Feature updates: pk_set, model, action
    """
    if action not in _feature_update_actions or raw:
        return
    ContentVariant = apps.get_model("spider_base", "ContentVariant")
    AssignedContent = apps.get_model("spider_base", "AssignedContent")

    if action == "_update" and created:
        instance.features.add(ContentVariant.objects.get(
            name="DefaultActions"
        ))

    if isinstance(instance, ContentVariant):
        # can be also the other side of the relation
        if instance.name in _ignored_features_for_update:
            return
        instances = model.objects.filter(pk__in=pk_set)
    else:
        instances = (instance,)

    if isinstance(instance, AssignedContent):
        # handled already by UpdateContentCb
        pass
    elif isinstance(model, AssignedContent):
        # fixup reverse relation by emulating UpdateContentCb
        for row in instances:
            # deduplicate
            UpdateContentCb(AssignedContent, row)
    else:
        for row in instances:
            # check if one feature depends on domain_mode
            if row.features.filter(
                ctype__contains=VariantType.domain_mode
            ):
                if not row.features.filter(name="DomainMode"):
                    row.features.add(ContentVariant.objects.get(
                        name="DomainMode"
                    ))
            elif row.features.filter(name="DomainMode"):
                row.features.remove(ContentVariant.objects.get(
                    name="DomainMode"
                ))
            # Persistence must not be removed automatically
            # if contents or features are persist add Persistence
            if ContentVariant.objects.filter(
                models.Q(assignedcontent__usercomponent=row) |
                models.Q(feature_for_components=row),
                ctype__contains=VariantType.persist
            ) and not row.features.filter(name="Persistence"):
                row.features.add(
                    ContentVariant.objects.get(name="Persistence")
                )


def UpdateSpiderCb(**_kwargs):
    # provided apps argument lacks model function support
    # so use default
    registry.contents.initialize()
    registry.protections.initialize()

    # regenerate info field
    AssignedContent = apps.get_model("spider_base", "AssignedContent")
    UserComponent = apps.get_model("spider_base", "UserComponent")
    ContentVariant = apps.get_model("spider_base", "ContentVariant")
    UserInfo = apps.get_model("spider_base", "UserInfo")

    UserComponent.objects.filter(name="index").update(strength=10)
    for row in AssignedContent.objects.all():
        try:
            row.content
        except ObjectDoesNotExist:
            logging.warning(
                "AssignedContent \"%s\" lacks content, remove.", row
            )
            row.delete()
            continue
        # works only with django.apps.apps
        row.info = row.content.get_info()
        if not row.token:
            row.token = create_b64_id_token(row.id, "_")
        if not row.content.expose_name or not row.name:
            row.name = row.content.get_content_name()
        if not row.content.expose_description:
            row.description = row.content.get_content_description()
        assert row.description is not None
        assert row.name is not None
        # triggers UpdateContentCb and FeaturesCb
        row.save(update_fields=['name', 'description', 'info', "token"])
        # regenerate references
        row.references.set(
            row.content.get_references()
        )

    for row in UserComponent.objects.all():
        if not row.token:
            row.token = create_b64_id_token(row.id, "_")
            row.save(update_fields=["token"])
        extra_variants = ContentVariant.objects.filter(
            models.Q(ctype__contains=VariantType.component_feature) &
            models.Q(ctype__contains=VariantType.feature_connect),
            assignedcontent__usercomponent=row
        )
        # triggers FeaturesCb so don't check features again
        row.features.add(*extra_variants)

    # force add default actions, special ignored by FeaturesCb
    default_actions = ContentVariant.objects.get(name="DefaultActions")
    default_actions.feature_for_components.add(
        *UserComponent.objects.exclude(
            features__name="DefaultActions"
        )
    )
    default_actions.feature_for_contents.add(
        *AssignedContent.objects.exclude(
            features__name="DefaultActions"
        )
    )

    for row in get_user_model().objects.filter(spider_info__isnull=True):
        UserInfo.objects.create(user=row)
        logger.warning("UserInfo had to be generated for %s", row)

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
            defaults={
                "state": ProtectionStateType.enabled
            }, protection=login
        )[0]

    if getattr(settings, "USE_CAPTCHAS", False):
        captcha = Protection.objects.filter(code="captcha").first()
        uc.protections.get_or_create(
            defaults={
                "state": ProtectionStateType.enabled
            }, protection=captcha
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


def DeleteFilesCb(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(False)
