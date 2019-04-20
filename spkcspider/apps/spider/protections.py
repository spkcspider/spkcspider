"""
installed_protections, add_protection
namespace: spider_base

"""

__all__ = ("installed_protections", "BaseProtection", "ProtectionResult",
           "initialize_protection_models")

from random import SystemRandom

from django.conf import settings
from django import forms
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from django.contrib.auth import authenticate
from django.views.decorators.debug import sensitive_variables
# from django.contrib.auth.hashers import make_password

from .helpers import add_by_field
from django.utils.crypto import constant_time_compare
from .constants import ProtectionType, ProtectionResult, index_names
from .fields import MultipleOpenChoiceField
from .widgets import OpenChoiceWidget

installed_protections = {}
_sysrand = SystemRandom()

# don't spam set objects
_empty_set = frozenset()

# for debug/min switch
_extra = '' if settings.DEBUG else '.min'


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

    UserComponent.objects.filter(name__in=index_names).update(strength=10)

    invalid_models = ProtectionModel.objects.exclude(
        code__in=installed_protections.keys()
    )
    if invalid_models.exists():
        print("Invalid protections, please update or remove them:",
              [t.code for t in invalid_models])


class BaseProtection(forms.Form):
    """
        Base for Protections
        Usage: use form to define some configurable fields for configuration
        use auth to validate: in this case:
            template_name, render, form variable are used
    """
    use_required_attribute = False
    active = forms.BooleanField(label=_("Active"), required=False)
    instant_fail = forms.BooleanField(
        label=_("Instant fail"), required=False,
        help_text=_("Fail instantly if not fullfilled. "
                    "Don't count to required_passes.")
    )
    # unique code name max 10 slug chars
    # if imported by extract_app_dicts, name is automatically set to key name
    # name = foo

    # ptype valid for, is overwritten with current ptype
    ptype = ProtectionType.access_control.value

    # description of Protection
    description = None

    template_name = None
    # form for authentication
    form = None
    # optional render function
    # render = None

    @classmethod
    def render_raw(cls, result):
        return {}

    # auto populated, instance
    protection = None
    instance = None

    # initial values
    initial = {}

    def __init__(self, protection, ptype, request, assigned=None, **kwargs):
        self.protection = protection
        self.ptype = ptype
        if assigned:
            self.instance = assigned.filter(protection=self.protection).first()
        initial = self.get_initial()
        # does assigned protection exist?
        if self.instance:
            # if yes force instance.active information
            initial["active"] = self.instance.active
            initial["instant_fail"] = self.instance.instant_fail
        super().__init__(initial=initial, **kwargs)
        self.fields["active"].help_text = self.description

    def get_initial(self):
        initial = self.initial.copy()
        if self.instance:
            initial.update(self.instance.data)
        return initial

    def get_strength(self):
        # can provide strength in range 0-4
        # 0 no protection
        # 1 weak protection
        # 2 normal protection
        # 3 strong protection
        # 4 reserved for login only, can be returned to auth user
        # tuple for min max
        return (1, 1)

    @staticmethod
    def extract_form_kwargs(request):
        kwargs = {}
        if request.method in ["POST", "PUT"]:
            kwargs = {
                'data': request.POST,
                'files': request.FILES,
            }
        return kwargs

    @classmethod
    def auth(cls, request, **kwargs):
        if hasattr(cls, "auth_form"):
            form = cls.auth_form(**cls.extract_form_kwargs(request))
            if form.is_valid():
                return 1
            return form
        return False

    @classmethod
    def localize_name(cls, name=None):
        if not name:
            name = cls.name
        return pgettext("protection name", name.title())

    @classmethod
    def auth_localize_name(cls, name=None):
        return cls.localize_name(name)

    def __str__(self):
        return self.localize_name(self.name)


# only friends have access
@add_by_field(installed_protections, "name")
class FriendProtection(BaseProtection):
    name = "friends"
    ptype = ProtectionType.access_control.value

    users = MultipleOpenChoiceField(
        label=_("Users"), required=False,
        widget=OpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )
    description = _("Limit access to selected users")

    def get_strength(self):
        return (3, 3)

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if (
            obj and
            (
                getattr(request.user, request.user.USERNAME_FIELD) in
                obj.data["users"]
            )
        ):
            return 3
        else:
            return False


@add_by_field(installed_protections, "name")
class RandomFailProtection(BaseProtection):
    name = "randomfail"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value
    ptype += ProtectionType.side_effects.value

    success_rate = forms.IntegerField(
        label=_("Success Rate"), min_value=20, max_value=100, initial=100,
        widget=forms.NumberInput(attrs={'type': 'range'}),
        help_text=_("Set success rate")
    )

    use_404 = forms.BooleanField(label="Use 404 errors?", required=False)

    description = _(
        "Fail/Refuse randomly. Optionally with 404 error, "
        "to disguise correct access."
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ProtectionType.authentication.value in self.ptype:
            # login should not be possible alone with it
            self.fields["instant_fail"].initial = True
            self.initial["instant_fail"] = True
            self.fields["instant_fail"].disabled = True

    def get_strength(self):
        if self.cleaned_data["success_rate"] > 70:
            return (0, 0)
        return (1, 1)

    @classmethod
    def localize_name(cls, name=None):
        return pgettext("protection name", "Random Fail")

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and obj.data.get("success_rate", None):
            if _sysrand.randrange(1, 101) <= obj.data["success_rate"]:
                return 0
            elif obj.data.get("use_404", False):
                raise Http404()
        return False


@add_by_field(installed_protections, "name")
class LoginProtection(BaseProtection):
    name = "login"
    ptype = ProtectionType.authentication.value
    ptype += ProtectionType.access_control.value

    description = _("Use Login password")

    allow_auth = forms.BooleanField(
        label=_("Component authentication"), required=False
    )

    class auth_form(forms.Form):
        use_required_attribute = False
        password = forms.CharField(
            label=_("Password"),
            strip=False,
            widget=forms.PasswordInput,
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ProtectionType.authentication.value in self.ptype:
            self.fields["active"].initial = True
            self.initial["active"] = True
            self.fields["active"].disabled = True
            del self.fields["allow_auth"]

    def get_strength(self):
        return (3, 4 if self.cleaned_data.get("allow_auth", False) else 3)

    @classmethod
    @sensitive_variables("password")
    def auth(cls, request, obj, **kwargs):
        if not obj:
            return cls.auth_form()

        username = obj.usercomponent.username
        for password in request.POST.getlist("password")[:2]:
            if authenticate(
                request, username=username, password=password, nospider=True
            ):
                if obj.data.get("allow_auth", False):
                    return 4
                return 3
        return cls.auth_form()

    @classmethod
    def auth_localize_name(cls, name=None):
        return cls.localize_name("Password")


@add_by_field(installed_protections, "name")
class PasswordProtection(BaseProtection):
    name = "password"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    description = _("Protect with extra passwords")
    prefix = "protection_passwords"

    class auth_form(forms.Form):
        use_required_attribute = False
        password = forms.CharField(
            label=_("Extra Password"),
            strip=False,
            widget=forms.PasswordInput,
        )

    passwords = MultipleOpenChoiceField(
        label=_("Passwords"), required=False,
        widget=OpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    auth_passwords = MultipleOpenChoiceField(
        label=_("Passwords (for component authentication)"), required=False,
        widget=OpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ProtectionType.authentication.value in self.ptype:
            del self.fields["auth_passwords"]

    @staticmethod
    def eval_strength(length):
        if not length:
            return 0
        elif length > 15:
            return 2
        elif length > 40:
            return 3
        return 1

    def get_strength(self):
        maxstrength = self.eval_strength(self.cleaned_data["max_length"])
        if len(self.cleaned_data["auth_passwords"]) > 0:
            maxstrength = 4
        return (
            self.eval_strength(self.cleaned_data["min_length"]),
            maxstrength
        )

    def clean_passwords(self):
        passwords = set()
        for pw in self.cleaned_data["passwords"]:
            if len(pw) > 0:
                passwords.add(pw)
        return list(passwords)

    def clean_auth_passwords(self):
        passwords = set()
        for pw in self.cleaned_data["auth_passwords"]:
            if self.eval_strength(len(pw)) >= 2:
                passwords.add(pw)
        return list(passwords)

    def clean(self):
        ret = super().clean()
        # prevents user self lockout
        if ProtectionType.authentication.value in self.ptype and \
           len(self.cleaned_data["passwords"]) == 0:
            self.cleaned_data["active"] = False

        min_length = None
        max_length = None

        for pw in self.cleaned_data.get("apasswords", _empty_set):
            lenpw = len(pw)
            if not min_length or lenpw < min_length:
                min_length = lenpw
            if not max_length or lenpw > max_length:
                max_length = lenpw

        for pw in self.cleaned_data.get("auth_passwords", _empty_set):
            lenpw = len(pw)
            if not min_length or lenpw < min_length:
                min_length = lenpw
            if not max_length or lenpw > max_length:
                max_length = lenpw
        ret["min_length"] = min_length
        ret["max_length"] = max_length
        return ret

    @classmethod
    @sensitive_variables("password", "pw")
    def auth(cls, request, obj, **kwargs):
        retfalse = cls.auth_form()
        if not obj:
            retfalse.fields["password"].label = _(
                "Extra Password (if required)"
            )
            return retfalse
        success = False
        auth = False
        max_length = 0
        for password in request.POST.getlist("password")[:2]:
            for pw in obj.data["passwords"]:
                if constant_time_compare(pw, password):
                    success = True
            if success:
                max_length = max(len(password), max_length)

        for password in request.POST.getlist("password")[:2]:
            for pw in obj.data["auth_passwords"]:
                if constant_time_compare(pw, password):
                    success = True
            if success:
                max_length = max(len(password), max_length)
                auth = True

        if success:
            if auth:
                return 4
            return cls.eval_strength(max_length)
        return retfalse


if getattr(settings, "USE_CAPTCHAS", False):
    from captcha.fields import CaptchaField

    @add_by_field(installed_protections, "name")
    class CaptchaProtection(BaseProtection):
        name = "captcha"
        ptype = ProtectionType.access_control.value
        ptype += ProtectionType.authentication.value
        description = _("Require captcha")

        class auth_form(forms.Form):
            use_required_attribute = False
            prefix = "protection_captcha"

        auth_form.declared_fields[settings.SPIDER_CAPTCHA_FIELD_NAME] = \
            CaptchaField(label=_("Captcha"))
        auth_form.base_fields[settings.SPIDER_CAPTCHA_FIELD_NAME] = \
            auth_form.declared_fields[settings.SPIDER_CAPTCHA_FIELD_NAME]

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if ProtectionType.authentication.value in self.ptype:
                # login should not be possible with captcha alone
                self.initial["instant_fail"] = True
                self.fields["instant_fail"].initial = True
                self.fields["instant_fail"].disabled = True
                self.fields["instant_fail"].help_text = \
                    _("instant_fail is for login required")

                if getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False):
                    self.initial["active"] = True
                    self.fields["active"].disabled = True
                    self.fields["instant_fail"].help_text = \
                        _("captcha is for login required (admin setting)")

        def get_strength(self):
            return (1, 1)

        @classmethod
        def localize_name(cls, name=None):
            return pgettext("protection name", "Captcha Protection")

        @classmethod
        def auth(cls, request, obj, **kwargs):
            if not obj:
                return cls.auth_form()
            form = cls.auth_form(**cls.extract_form_kwargs(request))
            if request.method != "GET" and form.is_valid():
                return 1
            return form


# travel protection
@add_by_field(installed_protections, "name")
class TravelProtection(BaseProtection):
    name = "travel"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    description = _("Deny access if valid travel protection is active")

    def get_strength(self):
        return (0, 0)

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj:
            from .models import TravelProtection as TravelProtectionContent
            travel = TravelProtectionContent.objects.get_active()
            # simple: disallow cannot be changed by user in fake mode
            travel = travel.filter(
                disallow__contains=obj.usercomponent
            )
            if not travel.exists():
                return 0
        return False
