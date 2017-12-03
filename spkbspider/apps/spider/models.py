"""
User Components, (Base)Contents and Protections
namespace: spiderucs

"""


from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


from jsonfield import JSONField

from .signals import test_success
from .protections import installed_protections


import logging

logger = logging.getLogger(__name__)

class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # special names:
    # index:
    #    protections are used for index
    #    attached content is only visible for admin and user
    # recovery (optional):
    #    protections are meaningless here (maybe later)
    #    attached content is only visible for admin, staff and user and can be used for recovery
    name = models.SlugField(max_length=50, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, editable=False)
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

    def auth_test(self, request, scope):
        for p in self.assigned.filter(can_test=True, active=True):
            if p.auth_test(request, scope):
                return True
        return False

    def settings(self, request):
        pall = []
        for p in self.assigned.all():
            pall.append(p.settings(request))
        return pall

    def get_absolute_url(self):
        return reverse("spiderucs:uc-view", kwargs={"user":self.user.username, "name":self.name})

    @property
    def is_protected(self):
        return self.name in ["index", "recovery"]


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
        pstart = self.info.find("%s=" % key)
        if pstart == -1:
            return None
        pend = self.info.find(";", len(key)+1)
        if pend == -1:
            raise Exception("Info field format broken (must end with ;): \"%s\"" % self.info)
        return self.info[pstart:pend]


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
    can_render = models.BooleanField(default=False)
    can_test = models.BooleanField(default=False)

    def __str__(self):
        return str(installed_protections[self.code])

class AssignedProtection(models.Model):
    id = models.BigAutoField(primary_key=True)
    protection = models.ForeignKey(Protection, on_delete=models.CASCADE, related_name="assigned", limit_choices_to={"code__in": installed_protections}, editable=False)
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
        return installed_protections[self.protection.code].auth_test(request=request, user=usercomponent.user, data=self.protectiondata, obj=self, scope=scope)

    def settings(self, request):
        if request.method == "GET":
            return installed_protections[self.protection.code](self.protectiondata, prefix=self.protection.code)
        else:
            prot = installed_protections[self.protection.code](request.POST, prefix=self.protection.code)
            if prot.is_valid():
                self.active = prot.cleaned_data.pop("active")
                self.protectiondata = prot.cleaned_data
                self.save()
            return prot

    def clean(self):
        installed_protections[self.protection.code].clean(self)
