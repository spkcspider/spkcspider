"""
installed_protections, add_protection
namespace: spider_base

"""

__all__ = ("add_protection", "ProtectionType", "check_blacklisted",
           "installed_protections", "BaseProtection", "ProtectionResult",
           "initialize_protection_models")

from collections import namedtuple
import enum
from random import SystemRandom

from django.conf import settings
from django import forms
from django.http import Http404
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import pgettext
from django.contrib.auth import authenticate


installed_protections = {}
_sysrand = SystemRandom()


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


def initialize_protection_models(apps=None):
    if not apps:
        from django.apps import apps
    UserComponent = apps.get_model("spider_base", "UserComponent")
    AssignedProtection = apps.get_model("spider_base", "AssignedProtection")
    ProtectionModel = apps.get_model("spider_base", "Protection")
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
    active = forms.BooleanField(label=_("Active"), required=False)

    # ptype valid for, is overwritten with current ptype
    ptype = ProtectionType.access_control.value

    # description of Protection
    description = None

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
        if assigned:
            self.instance = assigned.filter(protection=self.protection).first()
        initial = self.get_initial()
        # does assigned protection exist?
        if self.instance:
            # if yes force instance.active information
            initial["active"] = self.instance.active
        super().__init__(initial=initial, **kwargs)
        self.fields["active"].help_text = self.description

    def get_initial(self):
        initial = self.initial.copy()
        if self.instance:
            initial.update(self.instance.data)
        return initial

    @classmethod
    def auth(cls, **kwargs):
        return False

    @classmethod
    def localize_name(cls, name=None):
        if not name:
            name = cls.name
        return pgettext("protection name", name.title())

    def __str__(self):
        return self.localize_name(self.name)


def friend_query():
    return get_user_model().objects.filter(is_active=True)


# only friends have access
@add_protection
class FriendProtection(BaseProtection):
    name = "friends"
    ptype = ProtectionType.access_control.value
    users = forms.ModelMultipleChoiceField(
        label=_("Users"), queryset=friend_query(), required=False
    )
    description = _("Allow logged in users access to usercomponent")

    media = {
        'js': 'admin/js/vendor/select2/select2.full.min.js'
    }

    def clean_users(self):
        return [i.pk for i in self.cleaned_data["users"]]

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and request.user.pk in obj.data["users"]:
            return True
        else:
            return False


@add_protection
class RandomFailProtection(BaseProtection):
    name = "randomfail"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value
    success_rate = forms.IntegerField(
        label=_("Success Rate"), min_value=20, max_value=100, initial=100,
        widget=forms.NumberInput(attrs={'type': 'range'}),
        help_text=_("Set success rate")
    )
    description = _("Fail randomly with 404 error, to disguise correct access")

    @classmethod
    def localize_name(cls, name=None):
        return pgettext("protection name", "Random Fail")

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and obj.data.get("success_rate", None):
            if _sysrand.randrange(1, 101) <= obj.data["success_rate"]:
                return True
            else:
                raise Http404()
        return False


@add_protection
class RandomRefuseProtection(BaseProtection):
    name = "randomrefuse"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value
    success_rate = forms.IntegerField(
        label=_("Success Rate"), min_value=20, max_value=100, initial=100,
        widget=forms.NumberInput(attrs={'type': 'range'}),
        help_text=_("Set success rate")
    )

    description = "Refuse randomly, not so strong like Random Fail, can " + \
                  "be overvoted by other protection"

    @classmethod
    def localize_name(cls, name=None):
        return pgettext("protection name", "Random Refuse")

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and obj.data.get("success_rate", None):
            if _sysrand.randrange(1, 101) <= obj.data["success_rate"]:
                return True
        return False


@add_protection
class LoginProtection(BaseProtection):
    name = "login"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    description = _("Login as owner")

    class auth_form(forms.Form):
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


# @add_protection
class PasswordProtection(BaseProtection):
    name = "password"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    # should have hashing and salt? To be secure
    description = _("Use arbitary password")

    @classmethod
    def auth(cls, request, data, **kwargs):
        if request.POST.get("password", "") in data["passwords"]:
            return True
        else:
            return None


try:
    from captcha.fields import CaptchaField

    # @add_protection
    class CaptchaProtection(BaseProtection):
        # FIXME: broken for unknown reason, captcha is always invalid
        name = "captcha"
        ptype = ProtectionType.access_control.value
        description = _("Require captcha")

        class auth_form(forms.Form):
            prefix = "protection_captcha"
            sunglasses = CaptchaField(
                label=_("Captcha")
            )

        @classmethod
        def localize_name(cls, name=None):
            return pgettext("protection name", "Captcha Protection")

        @classmethod
        def auth(cls, request, obj, **kwargs):
            if not obj:
                return False
            form_kwargs = {}

            if request.method in ('POST', 'PUT'):
                form_kwargs.update({
                    'data': request.POST,
                })
            form = cls.auth_form(**form_kwargs)
            if form.is_valid():
                return True
            return None
except ImportError:
    pass
