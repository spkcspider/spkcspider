"""
User Components, (Base)Contents and Protections
namespace: spider_base

"""

import logging

from jsonfield import JSONField

from django.db import models
from django.conf import settings
from django.utils.translation import gettext as _
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

from .contents import installed_contents

from .protections import (
    installed_protections, ProtectionType, ProtectionResult
)


NONCE_SIZE = 10

try:
    from secrets import token_hex

    def token_nonce():
        return token_hex(NONCE_SIZE)
except ImportError:
    import binascii
    import os

    def token_nonce():
        return binascii.hexlify(
            os.urandom(NONCE_SIZE)
        ).decode('ascii')


logger = logging.getLogger(__name__)

_name_help = """
Name of the component.<br/>
Note: there are special named components
with different protection types and scopes.<br/>
Most prominent: "index" for authentication
"""


class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(default=token_nonce, max_length=NONCE_SIZE*2)
    # fix linter warning
    objects = models.Manager()
    # special name: index:
    #    protections are used for authentication
    #    attached content is only visible for admin and user
    name = models.SlugField(
        max_length=50,
        null=False,
        help_text=_name_help
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(null=True, default=None)
    contents = None
    # should be used for retrieving active protections, related_name
    protected_by = None
    protections = models.ManyToManyField(
        "spider_base.Protection", through="spider_base.AssignedProtection",
        related_name="usercomponents"
    )

    class Meta:
        unique_together = [("user", "name")]
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return "%s: %s" % (self.username, self.name)

    def auth(self, request, ptype=ProtectionType.access_control.value,
             protection_codes=None, **kwargs):
        return AssignedProtection.authall(
            request, self, ptype=ptype, protection_codes=protection_codes,
            **kwargs
        )

    def get_absolute_url(self):
        return reverse(
            "spider_base:ucontent-list",
            kwargs={
                "user": self.username, "name": self.name, "nonce": self.nonce
            }
        )

    @property
    def username(self):
        return getattr(self.user, self.user.USERNAME_FIELD)

    @property
    def is_protected(self):
        return self.name in ["index"]


def info_field_validator(value):
    prefixed_value = ";%s" % value
    if value[-1] != ";":
        raise ValidationError(
            _('%(value)s ends not with ;'),
            params={'value': value},
        )
    # check elements
    for elem in value[:-1].split(";"):
        f = elem.find("=")
        # flag
        if f != -1:
            elem = elem[:f]
        counts = 0
        counts += prefixed_value.count(";%s;" % elem)
        counts += prefixed_value.count(";%s=" % elem)
        assert(counts > 0)
        if counts > 1:
            raise ValidationError(
                _('multiple elements: %(element)s in %(value)s'),
                params={'element': elem, 'value': value},
            )


class UserContentVariant(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    ctype = models.CharField(
        max_length=10
    )
    code = models.CharField(max_length=255)
    name = models.SlugField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="+", null=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        unique_together = [
            ('owner', 'name')
        ]

    @property
    def installed_class(self):
        return installed_contents[self.code]

    @property
    def localized_name(self):
        if self.owner:
            return self.name
        return _(self.name)

    def __str__(self):
        return self.localized_name


class UserContent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(default=token_nonce, max_length=NONCE_SIZE*2)
    # fix linter warning
    objects = models.Manager()
    usercomponent = models.ForeignKey(
        UserComponent, on_delete=models.CASCADE,
        related_name="contents", null=False, blank=False
    )
    ctype = models.ForeignKey(
        UserContentVariant, editable=False, null=True,
        on_delete=models.SET_NULL
    )

    # creator = models.ForeignKey(
    #    settings.AUTH_USER_MODEL, editable=False, null=True,
    #    on_delete=models.SET_NULL
    # )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(null=True, default=None)
    # for extra information over content, admin only editing
    # format: flag1;flag2;foo=true;foo2=xd;...;endfoo=xy;
    # every section must end with ; every keyword must be unique and
    # in this format: keyword=
    # no unneccessary spaces!
    info = models.TextField(
        default=";", null=False, validators=[info_field_validator]
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, editable=False
    )
    object_id = models.BigIntegerField(editable=False)
    content = GenericForeignKey(
        'content_type', 'object_id', for_concrete_model=False
    )

    class Meta:
        unique_together = [
            ('content_type', 'object_id')
        ]
        indexes = [
            models.Index(fields=['usercomponent']),
            models.Index(fields=['object_id']),
        ]

    def get_flag(self, flag):
        if "%s;" % flag in self.info:
            return True
        return False

    def get_value(self, key):
        info = self.info
        pstart = info.find("%s=" % key)
        if pstart == -1:
            return None
        pend = info.find(";", pstart+len(key)+1)
        if pend == -1:
            raise Exception("Info field error: doesn't end with \";\": \"%s\""
                            % info)
        return info[pstart:pend]

    def get_absolute_url(self):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"id": self.id, "nonce": self.nonce, "access": "view"}
        )


class ProtectionManager(models.Manager):
    def invalid(self):
        return self.get_queryset().exclude(code__in=installed_protections)

    def valid(self):
        return self.get_queryset().filter(code__in=installed_protections)


# don't confuse with Protection objects used with add_protection
# this is pure DB
class Protection(models.Model):
    objects = ProtectionManager()
    usercomponents = None
    # autogenerated, no choices required
    code = models.SlugField(max_length=10, primary_key=True)
    # can only filter charfields
    ptype = models.CharField(
        max_length=10, default=ProtectionType.authentication.value
    )

    @property
    def installed_class(self):
        return installed_protections[self.code]

    def __str__(self):
        return str(self.installed_class)

    @sensitive_variables("kwargs")
    def auth(self, request, obj=None, **kwargs):
        # never ever allow authentication if not active
        if obj and not obj.active:
            return False
        # obj=None is for allow the sign to return False
        return self.installed_class.auth(
            obj=obj, request=request, **kwargs.copy()
        )

    @classmethod
    def authall_query(cls, request, query, required_passes=1,
                      **kwargs):
        ret = []
        for item in query:
            obj = None
            if hasattr(item, "protection"):  # is AssignedProtection
                item, obj = item.protection, item
            result = item.auth(
                request=request, obj=obj, **kwargs
            )
            if result is True:
                required_passes -= 1
            if result is not False:  # False will be not rendered
                ret.append(ProtectionResult(result, item))
        # don't require lower limit this way and
        # against timing attacks
        if required_passes <= 0:
            return True
        return ret

    @classmethod
    def authall(cls, request, required_passes=1,
                ptype=ProtectionType.authentication.value,
                protection_codes=None, **kwargs):
        """
            Usage: e.g. prerendering for login fields, because
            no assigned object is available there is no config
        """
        # allow is here invalid, no matter what ptype
        # allow has absolute no information in this case
        query = cls.objects.filter(ptype__contains=ptype).exclude(code="allow")
        if protection_codes:
            query = query.filter(
                code__in=protection_codes
            )
        passes = min(required_passes, len(query))
        return cls.auth_query(request, query, required_passed=passes)

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
    # django cannot serialize static, classmethods, so cheat
    ret = \
        {
            "code__in": Protection.objects.valid(),
            "ptype__contains": ProtectionType.access_control.value
        }
    if models.F("usercomponent__name") == "index":
        ret["ptype__contains"] = ProtectionType.authentication.value
    return ret


class AssignedProtection(models.Model):
    id = models.BigAutoField(primary_key=True)
    # fix linter warning
    objects = models.Manager()
    protection = models.ForeignKey(
        Protection, on_delete=models.CASCADE, related_name="assigned",
        limit_choices_to=get_limit_choices_assigned_protection, editable=False
    )
    usercomponent = models.ForeignKey(
        UserComponent, related_name="protected_by",
        on_delete=models.CASCADE, editable=False
    )
    # data for protection
    data = JSONField(default={}, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("protection", "usercomponent")]
        indexes = [
            models.Index(fields=['usercomponent']),
        ]

    @classmethod
    def authall(cls, request, usercomponent,
                ptype=ProtectionType.access_control.value,
                protection_codes=None, **kwargs):
        query = cls.objects.filter(
            protection__ptype__contains=ptype, active=True,
            usercomponent=usercomponent
        )
        # before protection_name check, for not allowing users
        # to manipulate required passes
        try:
            required_passes = min(
                len(query),  # if too many passes are required, lower
                query.get(protection__code="allow").data.get("passes", 1) + 1
            )
        except models.ObjectDoesNotExist:
            required_passes = 1
        return Protection.auth_query(
            request, query, required_passes=required_passes
        )

    @property
    def user(self):
        return self.usercomponent.user
