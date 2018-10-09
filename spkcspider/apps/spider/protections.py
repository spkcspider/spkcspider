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
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from django.contrib.auth import authenticate

from .helpers import cmp_pw, add_by_field
from .constants import ProtectionType, ProtectionResult


installed_protections = {}
_sysrand = SystemRandom()

# don't spam set objects
_empty_set = set()

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

    UserComponent.objects.filter(name="index", strength=0).update(strength=10)

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
                    "Don't count to required_passes. "
                    "Requires \"active\".")
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
        # 1 basic protection
        # 2 normal protection
        # 3 better protection
        # 4 strong protection
        return 1

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
                return True
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


def friend_query():
    return get_user_model().objects.filter(is_active=True)


# only friends have access
@add_by_field(installed_protections, "name")
class FriendProtection(BaseProtection):
    name = "friends"
    ptype = ProtectionType.access_control.value

    users = forms.ModelMultipleChoiceField(
        label=_("Users"), queryset=friend_query(), required=False
    )
    description = _("Limit access to selected users")

    def get_strength(self):
        return 4

    def clean_users(self):
        return [i.pk for i in self.cleaned_data["users"]]

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and request.user.pk in obj.data["users"]:
            return True
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
        if self.cleaned_data["success_rate"] > 90:
            return 0
        return 1

    @classmethod
    def localize_name(cls, name=None):
        return pgettext("protection name", "Random Fail")

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj and obj.data.get("success_rate", None):
            if _sysrand.randrange(1, 101) <= obj.data["success_rate"]:
                return True
            elif obj.data.get("use_404", False):
                raise Http404()
        return False


@add_by_field(installed_protections, "name")
class LoginProtection(BaseProtection):
    name = "login"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value
    # NEVER allow for computer access only to generate token

    description = _("Require login as owner")

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

    def get_strength(self):
        return 4

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if not obj:
            return cls.auth_form()

        username = obj.usercomponent.username
        password = request.POST.get("password", None)
        if authenticate(
            request, username=username, password=password,
            nospider=True
        ):
            return True
        else:
            return cls.auth_form()

    @classmethod
    def auth_localize_name(cls, name=None):
        return cls.localize_name("Password")


@add_by_field(installed_protections, "name")
class PasswordProtection(BaseProtection):
    name = "password"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    description = _("Protect with passwords")
    prefix = "protection_passwords"

    class auth_form(forms.Form):
        use_required_attribute = False
        password2 = forms.CharField(
            label=_("Password 2"),
            strip=False,
            widget=forms.PasswordInput,
        )

    passwords = forms.CharField(
        label=_("Passwords"),
        help_text=_("One password per line. Every password is stripped."),
        widget=forms.Textarea,
        strip=True, required=False,
        initial=""
    )

    def get_strength(self):
        if self.cleaned_data["min_length"] > 15:
            return 3
        return 2

    def clean_passwords(self):
        passwords = []
        for i in self.cleaned_data["passwords"].split("\n"):
            newpw = i.strip()
            if len(newpw) > 0:
                passwords.append(newpw)
        return "\n".join(passwords)

    def clean(self):
        ret = super().clean()
        if ProtectionType.authentication.value in self.ptype and \
           self.cleaned_data["passwords"] == "":
            self.cleaned_data["active"] = False
        min_length = None
        for pw in self.cleaned_data["passwords"].split("\n"):
            lenpw = len(pw)
            if not min_length or lenpw < min_length:
                min_length = lenpw
        ret["min_length"] = lenpw
        return ret

    @classmethod
    def auth(cls, request, obj, **kwargs):
        retfalse = cls.auth_form()
        if not obj:
            retfalse.fields["password2"].label = _("Password 2 (if required)")
            return retfalse
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        success = False
        for pw in obj.data["passwords"].split("\n"):
            if cmp_pw(pw, password):
                success = True
            if cmp_pw(pw, password2):
                success = True

        if success:
            return True
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
            sunglasses = CaptchaField(
                label=_("Captcha"),
            )

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
            return 1

        @classmethod
        def localize_name(cls, name=None):
            return pgettext("protection name", "Captcha Protection")

        @classmethod
        def auth(cls, request, obj, **kwargs):
            if not obj:
                return cls.auth_form()
            form = cls.auth_form(**cls.extract_form_kwargs(request))
            if request.method != "GET" and form.is_valid():
                return True
            return form


# travel protection
@add_by_field(installed_protections, "name")
class TravelProtection(BaseProtection):
    name = "travel"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    description = _("Fail if travel protection is active")

    def get_strength(self):
        return 0

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if obj:
            from .models import TravelProtection as TravelProtectionContent
            travel = TravelProtectionContent.objects.get_active().filter(
                usercomponent__user=obj.usercomponent.user,
                # only apply to younger TravelProtectionContent
                modified__gte=obj.modified
            )
            if not travel.exists():
                return True
        return False
