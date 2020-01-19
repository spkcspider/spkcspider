"""
Protection models, actual implementations are forms in protections
namespace: spider_base

"""

__all__ = ["Protection", "AssignedProtection", "AuthToken", "ReferrerObject"]

import logging

from django.conf import settings
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from jsonfield import JSONField

from spkcspider.constants import (
    MAX_TOKEN_B64_SIZE, ProtectionResult, ProtectionStateType, ProtectionType,
    TokenCreationError, hex_size_of_bigid
)
from spkcspider.utils.security import create_b64_id_token
from spkcspider.utils.urls import extract_host

from .. import registry
from ..abstract_models import BaseSubUserModel
from ..protections import ProtectionList, PseudoPw
from ..queryfilters import active_protections_q
from ..validators import validator_token

logger = logging.getLogger(__name__)


_striptoken = getattr(settings, "TOKEN_SIZE", 30)*4//3
# show 1/3 of token
_striptoken = _striptoken-_striptoken//3


class BaseProtectionQuerySet(models.QuerySet):
    @sensitive_variables("kwargs")
    def auth_query(self, request, required_passes=1, **kwargs):
        initial_required_passes = required_passes
        ret = ProtectionList()
        max_result = 0
        for item in self:
            obj = None
            _instant_fail = False
            if hasattr(item, "protection"):  # is AssignedProtection
                item, obj = item.protection, item
                _instant_fail = (obj.state == ProtectionStateType.instant_fail)
            # would be surprising if auth fails with required_passes == 0
            # achievable by required_passes = amount of protections
            if initial_required_passes == 0:
                _instant_fail = False
            result = item.auth(
                request=request, obj=obj, query=self,
                required_passes=initial_required_passes, **kwargs
            )
            if ProtectionType.password in item.ptype:
                ret.uses_password = True
            if _instant_fail:  # instant_fail does not reduce required_passes
                if type(result) is not int:  # False or form
                    # set limit unreachable
                    required_passes = len(self)
                else:
                    if result > max_result:
                        max_result = result
            elif type(result) is int:
                required_passes -= 1
                if result > max_result:
                    max_result = result
            if result is not False:  # False will be not rendered
                ret.media += item.installed_class.get_auth_media(result)
                ret.append(ProtectionResult(result, item))
        if ret.uses_password:
            p = PseudoPw()
            ret.insert(0, ProtectionResult(p, p))
            ret.media += p.media
        # after side effects like RandomFail with http404 errors
        if (
                request.GET.get("protection", "") == "false" and
                initial_required_passes > 0
           ):
            return False
        # don't require lower limit this way
        #   against timing attacks
        if required_passes <= 0:
            return max_result
        return ret


class ProtectionQuerySet(BaseProtectionQuerySet):

    def valid(self):
        return self.filter(code__in=registry.protections.keys())

    def invalid(self):
        return self.exclude(code__in=registry.protections.keys())

    def filter_protection_codes(self, protection_codes=None):
        if protection_codes is not None:
            return self.filter(
                models.Q(code__in=protection_codes) |
                models.Q(ptype__contains=ProtectionType.side_effects)
            )
        else:
            return self

    @sensitive_variables("kwargs")
    def authall(self, request, required_passes=1,
                ptype=ProtectionType.authentication,
                protection_codes=None, **kwargs):
        """
            Usage: e.g. prerendering for login fields, because
            no assigned object is available there is no config
        """
        query = self.filter(ptype__contains=ptype)

        # before protection_codes, for not allowing users
        # to manipulate required passes
        if required_passes > 0:
            # required_passes 1 and no protection means: login or token only
            required_passes = max(min(required_passes, len(query)), 1)
        else:
            # only side_effects now
            protection_codes = []

        query = query.filter_protection_codes(protection_codes)

        return query.order_by("code").auth_query(
            request, required_passes=required_passes,
            ptype=ptype
        )


class ReferrerObject(models.Model):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    url: str = models.URLField(
        max_length=(
            600 if (
                settings.DATABASES["default"]["ENGINE"] !=
                "django.db.backends.mysql"
            ) else 255
        ),
        db_index=True, unique=True, editable=False
    )

    objects = models.Manager()

    @cached_property
    def host(self):
        return extract_host(self.url)


# don't confuse with Protection objects used with add_protection
# this is pure DB
class Protection(models.Model):
    objects = ProtectionQuerySet.as_manager()
    # autogenerated, no choices required
    code = models.SlugField(max_length=10, primary_key=True, db_index=False)
    # protection abilities/requirements
    ptype = models.CharField(
        max_length=10, default=ProtectionType.authentication
    )

    @property
    def installed_class(self):
        return registry.protections[self.code]

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<Protection: %s>" % self.__str__()

    def localize_name(self):
        if self.code not in registry.protections:
            return self.code
        return self.installed_class.localize_name(self.code)

    def auth_localize_name(self):
        if self.code not in registry.protections:
            return self.code
        return self.installed_class.auth_localize_name(self.code)

    @sensitive_variables("kwargs")
    def auth(self, request, obj=None, **kwargs):
        # never ever allow authentication if not active
        assert not obj or obj.state != ProtectionStateType.disabled
        assert self.code in registry.protections, "invalid protection"
        return self.installed_class.auth(
            obj=obj, request=request, **kwargs.copy()
        )

    def get_form(self, prefix=None, **kwargs):
        if prefix:
            protection_prefix = "{}_protections_{{}}".format(prefix)
        else:
            protection_prefix = "protections_{}"
        return self.installed_class(
            protection=self, prefix=protection_prefix.format(self.code),
            **kwargs
        )

    @classmethod
    def get_forms(cls, ptype=None, **kwargs):
        protections = cls.objects.valid()
        if ptype:
            protections = protections.filter(ptype__contains=ptype)
        else:
            ptype = ""
        return map(lambda x: x.get_form(ptype=ptype, **kwargs), protections)


def get_limit_choices_assigned_protection():
    # django cannot serialize static, classmethods
    index = models.Q(usercomponent__strength=10)
    restriction = models.Q(
        ~index, ptype__contains=ProtectionType.access_control
    )
    restriction |= models.Q(
        index, ptype__contains=ProtectionType.authentication
    )
    return models.Q(code__in=Protection.objects.valid()) & restriction


class AssignedProtectionQuerySet(BaseProtectionQuerySet):

    def valid(self):
        return self.filter(protection__code__in=registry.protections.keys())

    def invalid(self):
        return self.exclude(protection__code__in=registry.protections.keys())

    def active(self):
        return self.filter(active_protections_q)

    def filter_protection_codes(self, protection_codes=None):
        if protection_codes is not None:
            return self.filter(
                models.Q(protection__code__in=protection_codes) |
                models.Q(
                    protection__ptype__contains=ProtectionType.side_effects
                )
            )
        else:
            return self

    def authall(
        self, request, required_passes=1,
        ptype=ProtectionType.access_control,
        protection_codes=None, **kwargs
    ):
        query = self.filter(
            active_protections_q,
            protection__ptype__contains=ptype
        )
        # before protection_codes, for not allowing users
        # to manipulate required passes
        if required_passes > 0:
            required_passes = max(
                min(
                    required_passes,
                    len(query.exclude(
                        state=ProtectionStateType.instant_fail
                    ))
                ), 1
            )
        elif ptype == ProtectionType.authentication:
            # enforce a minimum of required_passes, if auth (e.g. index)
            required_passes = 1
        else:
            required_passes = 0
            # only side_effects now
            protection_codes = []

        return query.filter_protection_codes(
            protection_codes
        ).auth_query(
            request, required_passes=required_passes, ptype=ptype
        )


class AssignedProtection(BaseSubUserModel):
    id: int = models.BigAutoField(primary_key=True)

    objects = AssignedProtectionQuerySet.as_manager()
    protection: Protection = models.ForeignKey(
        Protection, on_delete=models.CASCADE, related_name="assigned",
        limit_choices_to=get_limit_choices_assigned_protection
    )
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", related_name="protections",
        on_delete=models.CASCADE, editable=False
    )
    # data for protection
    data: dict = JSONField(default=dict, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    state: str = models.CharField(
        max_length=1, choices=ProtectionStateType.as_choices(),
        default=ProtectionStateType.enabled,
        help_text=_(
            "State of the protection."
        )
    )

    class Meta:
        unique_together = [("protection", "usercomponent")]

    def __str__(self):
        return "%s -> %s" % (
            self.usercomponent, self.protection.localize_name()
        )

    def __repr__(self):
        return "<Assigned: %s>" % (
            self.__str__()
        )


class AuthTokenManager(models.Manager):

    def create(self, *, token=None, **kwargs):
        if token:
            logger.warning("Should never specify token")
        ret = self.model(**kwargs)
        ret.save()
        return ret


class AuthToken(BaseSubUserModel):
    id: int = models.BigAutoField(primary_key=True, editable=False)
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="authtokens"
    )
    attached_to_content = models.ForeignKey(
        "spider_base.AssignedContent", on_delete=models.CASCADE,
        related_name="attachedtokens", null=True, blank=True
    )
    # -1=false,0=usercomponent,1-...=anchor
    persist: int = models.BigIntegerField(
        blank=True, default=-1, db_index=True
    )
    # brute force protection
    #  16 = id in hexadecimal
    #  +2 for seperators
    # when swapping tokens the id in the token can missmatch
    #  so don't rely on it
    token: str = models.CharField(
        max_length=MAX_TOKEN_B64_SIZE+hex_size_of_bigid+2,
        db_index=True, unique=True, null=True,
        validators=[
            validator_token
        ]
    )
    referrer = models.ForeignKey(
        "spider_base.ReferrerObject", on_delete=models.CASCADE,
        related_name="tokens", blank=True, null=True
    )
    session_key: str = models.CharField(max_length=40, null=True)
    extra: dict = JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    default_update_fields = None

    objects = AuthTokenManager()

    def __str__(self):
        return "{}...".format(self.token[:-_striptoken])

    def initialize_token(self):
        self.token = create_b64_id_token(
            self.id,
            "_",
            getattr(settings, "TOKEN_SIZE", 30)
        )

    def save(self, **kwargs):
        # maybe a little overengineered for that a clash can only happen
        # if an old generated token has the same token as a new one
        # the used id switched from the one of a usercomponent to the one
        # of the token
        start_token_creation = not self.token
        created = not self.id
        if start_token_creation:
            if not created:
                update_fields = set(kwargs.pop(
                    "update_fields", self.default_update_fields
                ))
                update_fields.discard("token")
                kwargs["update_fields"] = update_fields
            super().save(**kwargs)
            for i in range(0, 1000):
                if i >= 999:
                    # in reality this path will be very unlikely
                    if created:
                        self.delete()
                        self.token = None
                    raise TokenCreationError(
                        'A possible infinite loop was detected'
                    )
                self.initialize_token()
                try:
                    with transaction.atomic():
                        super().save(
                            update_fields=["token"],
                            using=kwargs.get("using")
                        )
                    break
                except IntegrityError:
                    pass
        else:
            super().save(**kwargs)


AuthToken.default_update_fields = frozenset(
    map(
        lambda field: field.attname,
        filter(
            lambda x: not x.primary_key and not hasattr(x, 'through'),
            AuthToken._meta.concrete_fields
        )
    )
)
