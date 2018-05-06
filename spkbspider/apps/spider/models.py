"""
User Components, (Base)Contents and Protections
namespace: spiderucs

"""


from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


from jsonfield import JSONField

from .signals import test_success
from .protections import installed_protections, ProtectionType


import logging
import typing

logger = logging.getLogger(__name__)

class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # fix linter warning
    objects = models.Manager()
    # special names:
    # index:
    #    protections are used for index
    #    attached content is only visible for admin and user
    # recovery (optional):
    #    protections are meaningless here (maybe later)
    #    attached content is only visible for admin, staff and user and can be used for recovery
    name = models.SlugField(max_length=50, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(null=True, default=None)
    contents = None
    # should be used for retrieving active protections, related_name
    assigned = None
    protections = models.ManyToManyField("spiderucs.Protection", through="spiderucs.AssignedProtection")
    class Meta:
        unique_together = [("user", "name"),]
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return self.name

    def auth_test(self, request, scope, ptype=ProtectionType.access_control):
        for p in self.assigned.filter(ptype=ptype, active=True):
            if p.auth_test(request, scope):
                return True
        return False

    def settings(self, dct=None):
        pall = []
        for p in self.assigned.all():
            pall.append(p.settings(dct))
        return pall

    #def get_absolute_url(self):
    #    return reverse("spiderucs:uc-view", kwargs={"user":self.user.username, "name":self.name})

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
        assert(counts>0)
        if counts > 1:
            raise ValidationError(
                _('multiple elements: %(element)s in %(value)s'),
                params={'element': elem, 'value': value},
            )

class UserContent(models.Model):
    id = models.BigAutoField(primary_key=True)
    # fix linter warning
    objects = models.Manager()
    usercomponent = models.ForeignKey(UserComponent, on_delete=models.CASCADE, editable=False, related_name="contents", null=False)

    #creator = models.ForeignKey(settings.AUTH_USER_MODEL, editable=False, null=True, on_delete=models.SET_ZERO)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(null=True, default=None)
    # for extra information over content, admin only editing
    # format: flag1;flag2;foo=true;foo2=xd;...;endfoo=xy;
    # every section must end with ; every keyword must be unique and in this format: keyword=
    # no unneccessary spaces!
    info = models.TextField(null=False, default=";", validators=[info_field_validator])
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False)
    object_id = models.BigIntegerField(editable=False)
    content = GenericForeignKey('content_type', 'object_id', for_concrete_model=False)
    class Meta:
        unique_together = [('content_type', 'object_id'),]
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
            raise Exception("Info field format broken (must end with ;): \"%s\"" % info)
        return info[pstart:pend]

    def get_absolute_url(self):
        return reverse("spiderucs:ucontent-view", kwargs={"user":self.user.username, "name":self.name, "id": self.id})


class ProtectionManager(models.Manager):
    def invalid(self):
        return self.get_queryset().exclude(code__in=installed_protections)

    def valid(self):
        return self.get_queryset().filter(code__in=installed_protections)


# don't confuse with Protection objects used with add_protection
# this is pure DB
class Protection(models.Model):
    objects = ProtectionManager()
    # autogenerated, no choices required
    code = models.SlugField(max_length=10, primary_key=True)
    # 0: access control, 1: authentication, 2: recovery
    ptype = models.PositiveIntegerField(default=ProtectionType.authentication)
    # type

    def __str__(self):
        return str(installed_protections[self.code])

class AssignedProtection(models.Model):
    def get_limit_choices(self=None):
        # django cannot serialize static, classmethods, so cheat
        ret = {"code__in": Protection.objects.valid(), "ptype__in": [0]}
        if models.F("usercomponent__name") == "index":
            ret["ptype__in"] = [1, 2]
        return ret

    id = models.BigAutoField(primary_key=True)
    # fix linter warning
    objects = models.Manager()
    protection = models.ForeignKey(Protection, on_delete=models.CASCADE, related_name="assigned", limit_choices_to=get_limit_choices, editable=False)
    usercomponent = models.ForeignKey(UserComponent, on_delete=models.CASCADE, editable=False)
    # data for protection
    protectiondata = JSONField(default={}, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    active = models.BooleanField(default=True)
    class Meta:
        unique_together = [("protection", "usercomponent"),]
        indexes = [
            models.Index(fields=['usercomponent']),
        ]


    #def get_absolute_url(self):
    #    return reverse("spiderucs:protection", kwargs={"user":self.usercomponent.user.username, "ucid":self.usercomponent.id, "pname": self.protection.code})

    def auth_test(self, request, scope):
        return installed_protections[self.protection.code].auth_test(request=request, user=self.usercomponent.user, data=self.protectiondata, obj=self, scope=scope)

    def settings(self, dct=None):
        if dct:
            return installed_protections[self.protection.code](dct, prefix=self.protection.code, assignedprotection=self)
        else:
            return installed_protections[self.protection.code](self.protectiondata, prefix=self.protection.code, assignedprotection=self)
