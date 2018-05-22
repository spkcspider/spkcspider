"""
User Components, (Base)Contents and Protections
namespace: spiderucs

"""

import logging

from jsonfield import JSONField

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from .protections import installed_protections, ProtectionType


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
        ordering = ["name"]

    def __str__(self):
        return self.name

    def auth_test(self, request, scope, ptype=ProtectionType.access_control):
        for p in self.assigned.filter(ptype=ptype, active=True):
            if p.auth_test(request, scope):
                return True
        return False

    def get_absolute_url(self):
        return reverse("spiderucs:ucontent-list", kwargs={"name":self.name})

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
        ordering = ["usercomponent", "id"]

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
        return reverse("spiderucs:ucontent-view", kwargs={"id": self.id})


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

    def get_form(self, data=None, files=None, auto_id='id_%s', prefix=None, *args, **kwargs):
        if prefix:
            protection_prefix = "{}_protections_{{}}".format(prefix)
        else:
            protection_prefix = "protections_{}"
        return installed_protections[self.code](*args, protection=self, data=data, files=files, auto_id=auto_id, prefix=protection_prefix.format(self.code), **kwargs)

    @classmethod
    def get_forms(cls, *args, ptypes=None, **kwargs):
        protections = cls.objects.valid()
        if ptypes:
            protections = protections.filter(code__in=ptypes)
        return map(lambda x: x.get_form(*args, **kwargs), protections)

def get_limit_choices_assigned_protection():
    # django cannot serialize static, classmethods, so cheat
    ret = {"code__in": Protection.objects.valid(), "ptype__in": [0]}
    if models.F("usercomponent__name") == "index":
        ret["ptype__in"] = [1, 2]
    return ret

class AssignedProtection(models.Model):
    id = models.BigAutoField(primary_key=True)
    # fix linter warning
    objects = models.Manager()
    protection = models.ForeignKey(Protection, on_delete=models.CASCADE, related_name="assigned", limit_choices_to=get_limit_choices_assigned_protection, editable=False)
    usercomponent = models.ForeignKey(UserComponent, related_name="protected_by", on_delete=models.CASCADE, editable=False)
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
