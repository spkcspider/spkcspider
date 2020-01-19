"""
Base for Contents
namespace: spider_base

"""

__all__ = [
    "ContentVariant", "AssignedContent"
]

import logging
from base64 import b64encode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django.apps import apps
from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from spkcspider.constants import (
    MAX_TOKEN_B64_SIZE, TravelProtectionType, VariantType,
    hex_size_of_bigid, static_token_matcher, travel_scrypt_params,
    ProtectionStateType
)
from spkcspider.utils.security import create_b64_id_token

from .. import registry
from ..abstract_models import BaseInfoModel, BaseSubUserModel
from ..queryfilters import travelprotection_types_q
from ..validators import content_name_validator, validator_token

logger = logging.getLogger(__name__)


login_choices_dict = dict(TravelProtectionType.as_choices())


# ContentType is already occupied
class ContentVariant(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    # usercontent abilities/requirements
    ctype: str = models.CharField(
        max_length=10, default="",
    )
    code: str = models.CharField(max_length=255)
    name: str = models.SlugField(max_length=50, unique=True, db_index=True)
    # required protection strength (selection)
    strength: int = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(10)]
    )
    # for content features
    valid_feature_for = models.ManyToManyField(
        "self", blank=True, related_name="valid_features", symmetrical=False
    )

    objects = models.Manager()

    @property
    def installed_class(self):
        return registry.contents[self]

    @property
    def feature_urls(self):
        return registry.feature_urls[self]

    @property
    def is_feature(self):
        return (
            VariantType.component_feature.value in self.ctype or
            VariantType.content_feature.value in self.ctype
        )

    @property
    def deletion_period(self):
        return registry.content_deletion_periods[self]

    def localize_name(self):
        if self not in registry.contents:
            return self.name
        return registry.contents[self].localize_name(self.name)

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<ContentVariant: %s>" % self.__str__()


class TravelProtectionManager(models.Manager):
    def get_active(self, now=None):
        if not now:
            now = timezone.now()
        AttachedTimespan = apps.get_model("spider_base", "AttachedTimespan")
        timespans = AttachedTimespan.objects.filter(
            models.Q(
                name="active",
                start__isnull=True,
                stop__gte=now
            ) |
            models.Q(
                name="active",
                start__lte=now,
                stop__isnull=True
            ) |
            models.Q(
                name="active",
                start__lte=now,
                stop__gte=now
            )
        )
        q = models.Q(info__contains="\x1eactive\x1e")
        q &= travelprotection_types_q
        q &= (
            models.Q(attachedtimespans__in=timespans) |
            models.Q(
                ctype__name="SelfProtection"
            )
        )
        return self.filter(q)

    def get_active_for_session(self, session, user, now=None):
        q = ~models.Q(info__contains="\x1epwhash=")
        if user.is_authenticated:
            for pw in session.get("travel_hashed_pws", []):
                q |= models.Q(
                    info__contains="\x1epwhash=%s\x1e" % pw
                )
            q &= models.Q(usercomponent__user=user)
        return self.get_active(now).filter(q)

    def get_active_for_request(self, request, now=None):
        return self.get_active_for_session(request.session, request.user)

    def handle_disable(self, travelprotection, request, now):
        return False

    def handle_trigger_hide(self, travelprotection, request, now):
        travelprotection.replace_info(
            travel_protection_type=TravelProtectionType.hide,
            pwhash=False
        )
        travelprotection.save(update_fields=["info"])
        return True

    def handle_trigger_disable(self, travelprotection, request, now):
        travelprotection.replace_info(
            travel_protection_type=TravelProtectionType.disable,
            pwhash=False
        )
        travelprotection.save(update_fields=["info"])
        return False

    def handle_wipe(self, travelprotection, request, now):
        # first components have to be deleted
        travelprotection.protect_components.all().delete()
        # as this deletes itself and therefor the information
        # about affected components
        travelprotection.protect_contents.all().delete()
        return True

    def handle_trigger_disable_user(self, travelprotection, request, now):
        AssignedProtection = \
            apps.get_model("spider_base", "AssignedProtection")
        UserComponent = \
            apps.get_model("spider_base", "UserComponent")
        travel = self.model.travel.get_active(now)
        q = models.Q(name="index")
        if travelprotection.content.free_data.get(
            "is_travel_protected", False
        ):
            q |= models.Q(travel_protected__in=travel)
        ucs = UserComponent.objects.select_for_update().exclude(q)
        ps = AssignedProtection.objects.select_for_update().filter(
            usercomponent__in=ucs
        )
        with transaction.atomic():
            ucs.update(
                strength=9, public=False
            )
            ucs.filter(required_passes=0).update(required_passes=1)
            ps.update(state=ProtectionStateType.disabled)
        travelprotection.replace_info(
            travel_protection_type=TravelProtectionType.disable,
            pwhash=False
        )
        travelprotection.save(update_fields=["info"])
        return False

    def handle_wipe_user(self, travelprotection, request, now):
        if travelprotection.content.free_data.get(
            "is_travel_protected", False
        ):
            return self.handle_trigger_disable_user(
                travelprotection, request, now
            )
        else:
            travelprotection.usercomponent.user.delete()
        return False

    _action_map = {
        val: "handle_%s" % key
        for key, val in TravelProtectionType.__members__.items()
    }

    def auth(self, request, uc, now=None):
        if not now:
            now = timezone.now()
        active = self.get_active(now).filter(
            usercomponent=uc
        )

        request.session["travel_hashed_pws"] = list(map(
            lambda x: b64encode(Scrypt(
                salt=settings.SECRET_KEY.encode("utf-8"),
                backend=default_backend(),
                **travel_scrypt_params
            ).derive(x[:128].encode("utf-8"))).decode("ascii"),
            request.POST.getlist("password")[:4]
        ))

        q = ~models.Q(info__contains="\x1epwhash=")
        for pw in request.session["travel_hashed_pws"]:
            q |= models.Q(
                info__contains="\x1epwhash=%s\x1e" % pw
            )

        active = active.filter(q)

        request.session["is_travel_protected"] = active.exists()

        # don't query further, use cached result (is_travel_protected)
        if not request.session["is_travel_protected"]:
            return True

        can_continue = True

        for travelprotection in active:
            travel_protection_type = \
                travelprotection.getlist("travel_protection_type", amount=1)[0]
            ret = getattr(
                self,
                self._action_map[travel_protection_type],
                lambda _1, _2, _3: True
            )(travelprotection, request, now)
            if not ret:
                can_continue = False
        return can_continue


class AssignedContentManager(models.Manager):
    """
        Manager for AssignedContent.
        Contains some base functionality for easing usage
        is not available in migrations
    """

    def create(self, **kwargs):
        ret = self.get_queryset().create(**kwargs)
        if not ret.token:
            ret.token = create_b64_id_token(ret.id, "_")
            ret.save(update_fields=["token"])
        return ret

    def update_or_create(self, **kwargs):
        ret = self.get_queryset().update_or_create(**kwargs)
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "_")
            ret[0].save(update_fields=["token"])
        return ret

    def get_or_create(self, defaults=None, **kwargs):
        ret = self.get_queryset().get_or_create(**kwargs)
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "_")
            ret[0].save(update_fields=["token"])
        return ret

    def from_token(
        self, token, *, info=frozenset(), variant=frozenset(),
        check_feature=False
    ):
        # check_feature requires that ctype of the selected content is in
        #  component features
        if isinstance(variant, str):
            variant = [variant]

        if isinstance(info, str):
            info = [info]

        q = models.Q()
        if variant:
            if isinstance(variant, models.QuerySet):
                q &= models.Q(ctype__in=variant)
            elif isinstance(variant, models.Model):
                q &= models.Q(ctype=variant)
            else:
                q &= models.Q(ctype__name__in=variant)
        for i in info:
            q &= models.Q(info__contains="\x1e%s\x1e" % i)
        if check_feature:
            q &= models.Q(
                ctype__feature_for_components__authtokens=token
            )
        return self.get(
            q, attached_to_token=token
        )

    def from_url_part(
        self, url, *, info=frozenset(), variant=frozenset(),
        check_feature=False
    ):
        """
            url: can be full url or token/accessmethod
            info: should be either string or iterable which will be matched
                  against info to retrieve an unique content
            returns: (<matched content/feature>, <content>/None)
        """
        UserComponent = apps.get_model("spider_base", "UserComponent")
        res = static_token_matcher.match(url)
        if not res:
            raise self.model.DoesNotExist()
        res = res.groupdict()
        # shortcut, we don't need to look up db to see that without
        # info field multiple items can match easily
        # the special case: only one content is unreliable and should
        # never tried to match
        if not info and not variant:
            raise self.model.MultipleObjectsReturned()

        if isinstance(variant, str):
            variant = [variant]

        if isinstance(info, str):
            info = [info]

        q = models.Q()
        if variant:
            if isinstance(variant, models.QuerySet):
                q &= models.Q(ctype__in=variant)
            elif isinstance(variant, models.Model):
                q &= models.Q(ctype=variant)
            else:
                q &= models.Q(ctype__name__in=variant)
        for i in info:
            q &= models.Q(info__contains="\x1e%s\x1e" % i)
        if res["access"] == "list":
            uc = UserComponent.objects.filter(
                token=res["static_token"]
            ).first()
            if check_feature:
                q &= (
                    models.Q(
                        ctype__feature_for_components=uc
                    )
                )
            return (self.get(q, usercomponent=uc), None)
        elif check_feature:
            content = self.get(
                token=res["static_token"]
            )
            q &= (
                models.Q(
                    ctype__feature_for_contents=content
                ) |
                models.Q(
                    ctype__feature_for_components__contents=content
                )
            )
            return (self.get(q), content)
        else:
            content = self.get(
                q, token=res["static_token"]
            )
            return (content, content)


class M2MTravelProtContent(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    source = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE, limit_choices_to=travelprotection_types_q
    )
    target = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE
    )


class M2MTravelProtComponent(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    source = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE, limit_choices_to=travelprotection_types_q
    )
    target = models.ForeignKey(
        "spider_base.UserComponent", related_name="+",
        on_delete=models.CASCADE, limit_choices_to={
            "strength__lt": 10,
        }
    )


class AssignedContent(BaseInfoModel, BaseSubUserModel):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    # fake_level = models.PositiveIntegerField(null=False, default=0)
    attached_to_token = models.ForeignKey(
        "spider_base.AuthToken", blank=True, null=True,
        on_delete=models.CASCADE
    )
    # don't use extensive recursion,
    # this can cause performance problems and headaches
    # this is not enforced for allowing some small chains
    # see SPIDER_MAX_EMBED_DEPTH setting for limits (default around 5)
    attached_to_content = models.ForeignKey(
        "self", blank=True, null=True,
        related_name="attached_contents", on_delete=models.CASCADE
    )
    # set to indicate creating a new token
    token_generate_new_size = None
    # brute force protection and identifier, replaces nonce
    #  16 = usercomponent.id in hexadecimal
    #  +1 for seperator
    token: str = models.CharField(
        max_length=(MAX_TOKEN_B64_SIZE)+hex_size_of_bigid+2,
        db_index=True, unique=True, null=True, blank=True,
        validators=[validator_token]
    )
    # regex disables controlcars and disable special spaces
    # and allows some of special characters
    name: str = models.CharField(
        max_length=255, blank=True, default="",
        validators=[
            content_name_validator
        ]
    )
    description: str = models.TextField(
        default="", blank=True
    )
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="contents", null=False, blank=False
    )
    features = models.ManyToManyField(
        "spider_base.ContentVariant",
        related_name="feature_for_contents", blank=True,
        limit_choices_to=models.Q(
            ctype__contains=VariantType.content_feature
        )
    )
    # ctype is here extended: VariantObject with abilities, name, model_name
    ctype = models.ForeignKey(
        ContentVariant, editable=False, null=True,
        on_delete=models.SET_NULL
    )
    priority: int = models.SmallIntegerField(default=0, blank=True)

    # creator = models.ForeignKey(
    #    settings.AUTH_USER_MODEL, editable=False, null=True,
    #    on_delete=models.SET_NULL
    # )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(
        null=True, blank=True, default=None
    )
    # required protection strength (real)
    strength = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(10)],
        editable=False
    )
    # required protection strength for links, 11 to disable links
    strength_link = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(11)],
        editable=False
    )
    attached_to_primary_anchor = models.BooleanField(
        default=False, editable=False, null=False,
        help_text=_(
            "Content references primary anchor"
        )
    )
    # - for a quick retrieval of related contents !!
    # - includes attached_contents
    # - is used by embed to find and output relations
    # - with get_forward_references can additional contents be added in embed
    references = models.ManyToManyField(
        "self", related_name="referenced_by", editable=False,
        symmetrical=False
    )

    protect_components = models.ManyToManyField(
        "spider_base.UserComponent",
        through=M2MTravelProtComponent, through_fields=("source", "target"),
        related_name="travel_protected",
        blank=True
    )
    protect_contents = models.ManyToManyField(
        "self", symmetrical=False,
        through=M2MTravelProtContent, through_fields=("source", "target"),
        related_name="travel_protected",
        blank=True
    )

    # info extra flags:
    #  primary: primary content of type for usercomponent
    #  unlisted: not listed
    #  anchor:
    objects = AssignedContentManager()
    travel = TravelProtectionManager()

    class Meta:
        constraints = []
        if (
            settings.DATABASES["default"]["ENGINE"] !=
            "django.db.backends.mysql"
        ):
            constraints.append(
                models.UniqueConstraint(
                    fields=['usercomponent', 'info'], name='unique_info'
                )
            )

    def __init__(self, *args, **kwargs):
        if isinstance(kwargs.get("ctype"), str):
            kwargs["ctype"] = ContentVariant.objects.get(name=kwargs["ctype"])
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<AssignedContent: ({}: {})>".format(
            self.usercomponent.username,
            self.name
        )

    def get_absolute_url(self, scope="view"):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"token": self.token, "access": scope}
        )

    # use next_object, last_object instead get_next_by_FOO, ...
    # for preventing disclosure of elements

    def get_size(self):
        return self.content.get_size()

    def localized_description(self):
        """ localize description either with own version or the localized """
        if not self.content:
            return self.description
        return self.content.localized_description()

    def clean(self):
        _ = gettext
        if VariantType.persist in self.ctype.ctype:
            if not self.attached_to_token:
                raise ValidationError(
                    _('Persistent token required'),
                    code="persist",
                )

        if self.strength > self.usercomponent.strength:
            raise ValidationError(
                _('Protection strength too low, required: %(strength)s'),
                code="strength",
                params={'strength': self.strength},
            )
        if (
            settings.DATABASES["default"]["ENGINE"] ==
            "django.db.backends.mysql"
        ):
            obj = AssignedContent.objects.filter(
                usercomponent=self.usercomponent,
                info=self.info
            ).first()

            if obj and obj.id != getattr(self, "id", None):
                raise ValidationError(
                    message=_("Unique Content already exists"),
                    code='unique_together',
                )
        super().clean()

    @cached_property
    def content(self):
        return self.ctype.installed_class.objects.get(associated=self)

    @property
    def is_hidden(self):
        return self.getflag("unlisted")

    @property
    def deletion_period(self):
        return self.ctype.deletion_period
