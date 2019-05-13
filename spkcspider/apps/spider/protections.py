"""
installed_protections, add_protection
namespace: spider_base

"""

__all__ = ("installed_protections", "BaseProtection", "ProtectionResult",
           "initialize_protection_models")

import logging
import binascii
from random import SystemRandom
from hashlib import sha256
from base64 import b64encode, b64decode
import ipaddress

from django.conf import settings
from django import forms

from django.apps import apps as django_apps
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from django.contrib.auth import authenticate
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables
# from django.contrib.auth.hashers import make_password

import ratelimit
from ratelimit import parse_rate
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .helpers import add_by_field, create_b64_token, aesgcm_pbkdf2_cryptor
from .constants import ProtectionType, ProtectionResult
from .fields import MultipleOpenChoiceField
from .widgets import OpenChoiceWidget, PWOpenChoiceWidget

logger = logging.getLogger(__name__)
installed_protections = {}
_sysrand = SystemRandom()

# don't spam set objects
_empty_set = frozenset()

# for debug/min switch
_extra = '' if settings.DEBUG else '.min'

_pbkdf2_params = {
    "iterations": 120000,
    "hash_name": "sha512",
    "dklen": 32
}

_Scrypt_params = {
    "length": 64,
    "n": 2**14,
    "r": 16,
    "p": 2,
}


def initialize_protection_models(apps=None):
    if not apps:
        apps = django_apps
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

    # auto populated, instance
    protection = None
    instance = None
    usercomponent = None
    parent_form = None

    # initial values
    initial = {}

    def __init__(self, *, protection, ptype, request, uc, form, **kwargs):
        AssignedProtection = django_apps.get_model(
            "spider_base", "AssignedProtection"
        )
        self.ptype = ptype
        self.parent_form = form
        self.instance = uc.protections.filter(
            protection=protection
        ).first()
        if not self.instance:
            self.instance = AssignedProtection(
                usercomponent=uc, protection=protection, active=False
            )
        initial = self.get_initial()
        # use instance informations
        initial["active"] = self.instance.active
        initial["instant_fail"] = self.instance.instant_fail
        # copy of initial is saved as self.initial, so safe to change it
        # after __init__ is called
        super().__init__(initial=initial, **kwargs)
        self.fields["active"].help_text = self.description

    def get_initial(self):
        initial = self.initial.copy()
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

    def save(self):
        self.instance.active = self.cleaned_data.pop("active")
        self.instance.instant_fail = self.cleaned_data.pop("instant_fail")
        self.instance.data = self.cleaned_data
        self.instance.save()


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
            obj and request.user.is_authenticated and
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

    def get_strength(self):
        return (0, 0)

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
class RateLimitProtection(BaseProtection):
    name = "ratelimit"
    ptype = ProtectionType.access_control.value
    ptype += ProtectionType.authentication.value

    rate_accessed = forms.RegexField(
        regex=r'([\d]+)/([\d]*)([smhd])?',
        required=False,
        help_text=_(
            "Maximal access tries to this component per ip "
            "before blocking. Format: tries/multiplier"
            "(smhdw, second till week)"
        )
    )
    rate_static_token_error = forms.IntegerField(
        required=False, min_value=1,
        help_text=_(
            "Maximal http404 errors per hour per user/ip before blocking"
        )
    )
    rate_login_failed_ip = forms.IntegerField(
        required=False, min_value=1,
        help_text=_(
            "Maximal failed logins per ip per hour before blocking"
        )
    )
    rate_login_failed_account = forms.IntegerField(
        required=False, min_value=1,
        help_text=_(
            "Maximal failed logins per hour for this user before blocking. "
            "Useful for login"
        )
    )

    description = _(
        "Ratelimit access tries"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ProtectionType.authentication.value in self.ptype:
            pass

    def get_strength(self):
        return (1, 1)

    def clean_rate_accessed(self):
        try:
            ret = parse_rate(self.cleaned_data.get("rate_accessed"))
            if ret[0] <= 0 or ret[1] <= 0:
                return None
        except ValueError:
            return None
        return self.cleaned_data.get("rate_accessed")

    @classmethod
    def localize_name(cls, name=None):
        return pgettext("protection name", "Rate Limit")

    @classmethod
    def count_access(cls, request, obj):
        return b"%b:%b" % (
            str(obj.usercomponent.pk).encode("ascii"), ipaddress.ip_network(
                request.META['REMOTE_ADDR'], strict=False
            ).compressed.encode("ascii")
        )

    @classmethod
    def auth(cls, request, obj, **kwargs):
        if not obj:
            return False
        if obj:
            temp = obj.data.get("rate_accessed", None)
            if temp and ratelimit.get_ratelimit(
                request=request, group="spider_ratelimit_accessed",
                key=cls.count_access(request, obj), rate=temp, inc=True
            )["request_limit"] > 0:
                return False
            temp = obj.data.get("rate_static_token_error", None)
            if temp and ratelimit.get_ratelimit(
                request=request, group="spider_static_token_error",
                key="user_or_ip", rate=(int(temp), 3600), inc=False
            )["request_limit"] > 0:
                return False
            temp = obj.data.get("rate_login_failed_ip", None)
            if temp and ratelimit.get_ratelimit(
                request=request, group="spider_login_failed_ip",
                key="ip", rate=(int(temp), 3600), inc=False
            )["request_limit"] > 0:
                return False
            temp = obj.data.get("rate_login_failed_account", None)
            if temp and ratelimit.get_ratelimit(
                request=request, group="spider_login_failed_account",
                key=lambda x, y: obj.usercomponent.username,
                rate=(int(temp), 3600), inc=False
            )["request_limit"] > 0:
                return False
        return 1


@add_by_field(installed_protections, "name")
class LoginProtection(BaseProtection):
    name = "login"
    ptype = ProtectionType.authentication.value
    ptype += ProtectionType.access_control.value

    description = _("Use Login password")

    allow_auth = forms.BooleanField(
        label=_("Component authentication"), required=False
    )
    _request = None

    class auth_form(forms.Form):
        use_required_attribute = False
        password = forms.CharField(
            label=_("Password"),
            strip=False,
            widget=forms.PasswordInput,
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._request = kwargs.get("request")
        if ProtectionType.authentication.value in self.ptype:
            self.fields["active"].initial = True
            self.initial["active"] = True
            self.fields["active"].disabled = True
            del self.fields["allow_auth"]

    def clean(self):
        super().clean()
        if ProtectionType.authentication.value in self.ptype:
            if not authenticate(
                self._request, username=self.instance.usercomponent.username,
                password=self.parent_form.initial["master_pw"], nospider=True
            ):
                self.parent_form.add_error(
                    "master_pw",
                    forms.ValidationError(
                        _("Invalid Password"),
                        code="invalid_password"
                    )
                )
        return self.cleaned_data

    def get_strength(self):
        return (3, 4 if self.cleaned_data.get("allow_auth", False) else 3)

    @classmethod
    @sensitive_variables("password")
    def auth(cls, request, obj, **kwargs):
        if not obj:
            return cls.auth_form()

        username = obj.usercomponent.username
        for password in request.POST.getlist("password")[:4]:
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

    class Media:
        css = {
            'all': [
                'node_modules/select2/dist/css/select2.min.css'
            ]
        }
        js = [
            'node_modules/base64-js/base64js.min.js',
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            'node_modules/select2/dist/js/select2%s.js' % _extra,
            'spider_base/protections/PasswordProtection.js'
        ]

    class auth_form(forms.Form):
        use_required_attribute = False
        password = forms.CharField(
            label=_("Extra Password"),
            strip=False,
            widget=forms.PasswordInput,
        )

    salt = forms.CharField(
        widget=forms.HiddenInput
    )
    default_master_pw = forms.CharField(
        widget=forms.HiddenInput, disabled=True
    )

    passwords = MultipleOpenChoiceField(
        label=_("Passwords"), required=False,
        widget=PWOpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    auth_passwords = MultipleOpenChoiceField(
        label=_("Passwords (for component authentication)"), required=False,
        widget=PWOpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    _successful_clean = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        salt = self.initial.get("salt")
        if not salt:
            salt = self.fields["salt"].widget.value_from_datadict(
                self.data, self.files, self.add_prefix("salt")
            )
        if not salt:
            salt = create_b64_token()
        self.initial["salt"] = salt
        self.initial["default_master_pw"] = sha256(
            "".join([salt, settings.SECRET_KEY]).encode("utf-8")
        ).hexdigest()
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

    @classmethod
    def hash_pw(cls, pw, salt, params=_Scrypt_params):
        return b64encode(Scrypt(
            salt=salt,
            backend=default_backend(),
            **params
        ).derive(pw[:128].encode("utf-8"))).decode("ascii")

    def is_valid(self):
        if not self._successful_clean:
            return False
        return super().is_valid()

    def clean(self):
        super().clean()
        # prevents user self lockout
        if ProtectionType.authentication.value in self.ptype and \
           len(self.cleaned_data["passwords"]) == 0:
            self.cleaned_data["active"] = False
        elif (
            len(self.cleaned_data["passwords"]) == 0 and
            len(self.cleaned_data["auth_passwords"]) == 0
        ):
            self.cleaned_data["active"] = False

        if getattr(self.instance, "id", None) and not self.has_changed():
            self.cleaned_data.update(self.instance.data)
            self._successful_clean = True
            return self.cleaned_data

        # eliminate duplicates
        self.cleaned_data["passwords"] = list(set(
            self.cleaned_data.get("passwords", _empty_set)
        ))
        self.cleaned_data["auth_passwords"] = list(set(
            self.cleaned_data.get("auth_passwords", _empty_set)
        ))
        self.cleaned_data["pbkdf2_params"] = _pbkdf2_params

        min_length = None
        max_length = None
        cryptor = None
        salt = self.cleaned_data.get("salt", "").encode("ascii")
        if not salt:
            return self.cleaned_data
        master_pw = self.parent_form.initial.get("master_pw", None)
        self.cleaned_data.pop("default_master_pw", None)
        has_master_pw = True
        if not master_pw:
            has_master_pw = False
            master_pw = self.initial["default_master_pw"]
        cryptor = aesgcm_pbkdf2_cryptor(
            master_pw, salt=salt,
            params=self.cleaned_data["pbkdf2_params"]
        )

        hashed_passwords = []
        auth_passwords = []
        hashed_auth_passwords = []
        current_field = "passwords"
        try:
            for pw in self.cleaned_data["passwords"]:
                if pw.startswith("bogo"):
                    raise ValueError("bogo not allowed here")
                nonce, pw = map(b64decode, pw.split(":", 1))
                pw = cryptor.decrypt(nonce, pw, None).decode("utf-8")
                lenpw = len(pw)
                if not min_length or lenpw < min_length:
                    min_length = lenpw
                if not max_length or lenpw > max_length:
                    max_length = lenpw
                hashed_passwords.append(self.hash_pw(
                    pw, salt, params=_Scrypt_params
                ))

            current_field = "auth_passwords"

            for pw in self.cleaned_data["auth_passwords"]:
                if pw.startswith("bogo"):
                    raise ValueError("bogo not allowed here")
                pwsource = pw
                nonce, pw = map(b64decode, pw.split(":", 1))
                pw = cryptor.decrypt(nonce, pw, None).decode("utf-8")
                lenpw = len(pw)
                if self.eval_strength(lenpw) < 2:
                    continue
                if not min_length or lenpw < min_length:
                    min_length = lenpw
                if not max_length or lenpw > max_length:
                    max_length = lenpw
                auth_passwords.append(pwsource)
                hashed_auth_passwords.append(self.hash_pw(
                    pw, salt, params=_Scrypt_params
                ))

            self.cleaned_data["hashed_passwords"] = hashed_passwords
            self.cleaned_data["auth_passwords"] = auth_passwords
            self.cleaned_data["scrypt_params"] = _Scrypt_params
            self.cleaned_data["hashed_auth_passwords"] = hashed_auth_passwords
            self.cleaned_data["min_length"] = min_length
            self.cleaned_data["max_length"] = max_length
            self._successful_clean = True
        except InvalidTag:
            if has_master_pw:
                self.parent_form.add_error(
                    "master_pw",
                    forms.ValidationError(
                        _(
                            "Invalid master password? "
                            "Passwords were not readable"
                        )
                    )
                )
            else:
                self.add_error(
                    current_field,
                    forms.ValidationError(
                        _(
                            "Forgot to enter master password? "
                            "Passwords were not readable"
                        )
                    )
                )
        except (ValueError, binascii.Error) as exc:
            logger.warning("PWProtection: pw encoding problems", exc_info=exc)
            self.add_error(
                current_field,
                forms.ValidationError(
                    _("Format error, check passwords")
                )
            )

        return self.cleaned_data

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
        salt = obj.data.get("salt", "").encode("ascii")
        for password in request.POST.getlist("password")[:4]:
            if salt:
                pwhash = cls.hash_pw(
                    password, salt, params=obj.data.get(
                        "scrypt_params", _Scrypt_params
                    )
                )

                for pw in obj.data["hashed_passwords"]:
                    if constant_time_compare(pw, pwhash):
                        success = True

                for pw in obj.data["hashed_auth_passwords"]:
                    if constant_time_compare(pw, pwhash):
                        success = True
                        auth = True
            else:

                for pw in obj.data["passwords"]:
                    if constant_time_compare(pw, password):
                        success = True

                for pw in obj.data.get("auth_passwords", []):
                    if constant_time_compare(pw, password):
                        success = True
                        auth = True
            if success:
                max_length = max(len(password), max_length)

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
