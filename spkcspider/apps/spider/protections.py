"""
installed_protections, add_protection
namespace: spider_base

"""

__all__ = ("add_protection", "ProtectionType", "check_blacklisted",
           "installed_protections", "BaseProtection", "ProtectionResult",
           "initialize_protection_models")

from collections import namedtuple
import enum

from django.conf import settings
from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import authenticate


installed_protections = {}


class ProtectionType(str, enum.Enum):
    # receives: request, scope
    access_control = "a"
    # receives: request, scope, password
    authentication = "b"
    # forget about recovery, every recovery method is authentication
    # and will be misused this way
    # The only real recovery is by staff and only if there is a secret


def check_blacklisted(name):
    if name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
        return False
    return True


def add_protection(klass):
    if klass.name != "allow":
        if klass.name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
            return klass
    if klass.name in installed_protections:
        raise Exception("Duplicate protection name")
    installed_protections[klass.name] = klass
    return klass


def initialize_protection_models():
    from .models import UserComponent, AssignedProtection
    from .models import Protection as ProtectionModel
    for code, val in installed_protections.items():
        ret = ProtectionModel.objects.get_or_create(
            defaults={"ptype": val.ptype}, code=code
        )[0]
        if ret.ptype != val.ptype:
            ret.ptype = val.ptype
            ret.save()
    temp = ProtectionModel.objects.exclude(
        code__in=installed_protections.keys()
    )

    login = ProtectionModel.objects.filter(code="login").first()
    if login:
        for uc in UserComponent.objects.filter(name="index"):
            asuc = AssignedProtection.objects.get_or_create(
                defaults={"active": True},
                usercomponent=uc, protection=login
            )[0]
            if not asuc.active:
                asuc.active = True
                asuc.save()
    if temp.exists():
        print("Invalid protections, please update or remove them:",
              [t.code for t in temp])


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])


class BaseProtection(forms.Form):
    """
        Base for Protections
        Usage: use form to define some configurable fields for configuration
        use auth to validate: in this case:
            template_name, render, form variable are used
    """
    active = forms.BooleanField(required=False)

    # ptype valid for, is overwritten with current ptype
    ptype = ProtectionType.access_control.value

    template_name = None
    # form for authentication
    form = None
    # optional render function
    # render = None

    # auto populated, instance
    protection = None
    instance = None

    # initial values
    initial = {}

    def __init__(self, protection, ptype, assigned=None, **kwargs):
        self.protection = protection
        self.ptype = ptype
        initial = self.initial.copy()
        if assigned:
            self.instance = assigned.filter(protection=self.protection).first()
            # does assigned protection exist?
            if self.instance:
                initial["active"] = self.instance.active
        super().__init__(initial=initial, **kwargs)

    @classmethod
    def auth(cls, **kwargs):
        return False


# if specified with multiple protections all protections must be fullfilled
@add_protection
class AllowProtection(BaseProtection):
    name = "allow"
    ptype = ProtectionType.access_control.value
    passes = forms.IntegerField(
        initial=None, required=False,
        help_text="How many protection passes are required?"
    )

    @classmethod
    def auth(cls, **_kwargs):
        return True

    def __str__(self):
        return _("Allow")


def friend_query():
    return get_user_model().objects.filter(is_active=True)


# only friends have access
@add_protection
class FriendProtection(BaseProtection):
    name = "friends"
    ptype = ProtectionType.access_control.value
    users = forms.ModelMultipleChoiceField(
        queryset=friend_query(), required=False
    )

    media = {
        'js': 'admin/js/vendor/select2/select2.full.min.js'
    }

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if request.user.pk in obj.data["users"]:
            return True
        else:
            return False

    def __str__(self):
        return _("Friends")


@add_protection
class LoginProtection(BaseProtection):
    name = "login"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    class form(forms.Form):
        password = forms.CharField(
            label=_("Password"),
            strip=False,
            widget=forms.PasswordInput,
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ProtectionType.authentication.value in self.ptype:
            self.fields["active"].initial = True
            self.fields["active"].disabled = True

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if not obj:
            return None
        username = obj.usercomponent.username
        if username != request.POST.get("username", ""):
            username = None
        password = request.POST.get("password", None)
        if authenticate(
            request, username=username, password=password,
            nospider=True
        ):
            return True
        else:
            return None

    def __str__(self):
        return _("Login authentication")


# @add_protection
class PasswordProtection(BaseProtection):
    name = "pw"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    @classmethod
    def auth(cls, request, data, **kwargs):
        if request.POST.get("password", "") in data["passwords"]:
            return True
        else:
            return None

    def __str__(self):
        return _("Password based authentication")
