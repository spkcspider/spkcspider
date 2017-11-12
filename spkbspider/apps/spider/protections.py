"""
installed_protections, add_protection
namespace: spiderucs

"""

__all__ = ["add_protection", "check_blacklisted", "installed_protections"]

from django.http.response import HttpResponseForbidden
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from django.contrib.auth import get_user_model


try:
    import jwt
except ImportError:
    jwt = None


installed_protections = {}

def check_blacklisted(name):
    if klass.name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
        return False
    return True

def add_protection(klass):
    if klass.name != "deny":
        if klass.name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
            return klass
    if klass.name in installed_protections:
        raise Exception("Duplicate protection name")
    installed_protections[klass.name] = klass
    return klass

# form with inner form for authentication
class BaseProtection(forms.Form):
    active = forms.BooleanField(required=True)
    can_render = False
    @classmethod
    def auth_test(cls, **kwargs):
        return False
    @classmethod
    def auth_render(cls, **kwargs):
        return None

# if specified with multiple protections all protections must be fullfilled
@add_protection
class AllowProtection(BaseProtection):
    name = "allow"

    @classmethod
    def auth_test(cls, request, **kwargs):
        return True
    def __str__(self):
        return _("Allow")


def friend_query():
    return get_user_model().objects.filter(active=True)
# only friends have access
@add_protection
class FriendProtection(BaseProtection):
    name = "friends"
    users = forms.ModelMultipleChoiceField(queryset=friend_query)
    @classmethod
    def auth_test(cls, request, data, **kwargs):
        if request.user.id in data["users"]:
            return True
        else:
            return False

    def __str__(self):
        return _("Friends")

@add_protection
class PasswordProtection(BaseProtection):
    name = "pw"

    @classmethod
    def auth_test(cls, request, data, **kwargs):
        if request.POST.get("password", "") in data["passwords"]:
            return True
        else:
            return False

    def __str__(self):
        return _("Password based authentication")

@add_protection
class AuditPasswordProtection(object):
    name = "auditpw"

    @classmethod
    def auth_test(cls, request, data, obj, **kwargs):
        if "user" not in request.POST:
            return False
        user = request.POST["user"]
        if "password" not in request.POST:
            return False
        if user not in data["users"]:
            return False
        pwhash = request.POST["password"]
        if data["users"][user] == pwhash:
            if "audit" not in data:
                data["audit"] = []
            data["audit"].append(())
            obj.save()
            return True
        else:
            return False

    def __str__(self):
        return _("Audited pw based authentication")



if jwt:
    @add_protection
    class JWTProtection(object):
        name = "jwt"
        def validate(self, request, data, **kwargs):
            if request.user.username in data.get("users", []):
                return True
            else:
                return False

        def render(self, request, obj, **kwargs):
            return redirect_to_login(redirect(obj), settings.LOGIN_URL, REDIRECT_FIELD_NAME)

        def __str__(self):
            return _("JWT Authentification")
