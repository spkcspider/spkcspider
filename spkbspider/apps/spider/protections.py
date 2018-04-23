"""
installed_protections, add_protection
namespace: spiderucs

"""

__all__ = ["add_protection", "check_blacklisted", "installed_protections", "BaseProtection"]

from django.http.response import HttpResponseForbidden
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from django.contrib.auth import get_user_model
from django.views.decorators.debug import sensitive_variables


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
    if klass.name != "allow":
        if klass.name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
            return klass
    if klass.name in installed_protections:
        raise Exception("Duplicate protection name")
    installed_protections[klass.name] = klass
    return klass

# form with inner form for authentication
class BaseProtection(forms.Form):
    active = forms.BooleanField(required=True)

    # ptype= 0: access control, 1: authentication, 2: recovery
    # 1, 2 require render
    ptype = 0

    template_name = None
    template_engine = None
    response_class = TemplateResponse
    content_type = None

    # auto populated
    assignedprotection = None

    def __init__(self, *args, **kwargs):
        self.assignedprotection = kwargs.pop("assignedprotection")
        super().__init__(*args, **kwargs)

    def get_data(self):
        return self.cleaned_data

    def save(self)::
        self.assignedprotection.active = self.cleaned_data.pop("active")
        self.assignedprotection.protectiondata = self.get_data()
        self.assignedprotection.save(update_fields=["active","protectiondata"])

    @classmethod
    def auth_test(cls, **kwargs):
        return False

    @classmethod
    def render(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def render_template(cls, request, context, **response_kwargs):
        response_kwargs.setdefault('content_type', cls.content_type)
        return cls.response_class(
            request=request,
            template=cls.get_template_names(),
            context=context,
            using=cls.template_engine,
            **response_kwargs)

    @classmethod
    def get_template_names(cls):
        if cls.template_name:
            return [cls.template_name]
        else:
            return

# if specified with multiple protections all protections must be fullfilled
@add_protection
class AllowProtection(BaseProtection):
    name = "allow"
    ptype = 0

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
    ptype = 0
    @classmethod
    def auth_test(cls, request, data, **kwargs):
        if request.user.id in data["users"]:
            return True
        else:
            return False

    def __str__(self):
        return _("Friends")

#@add_protection
class PasswordProtection(BaseProtection):
    name = "pw"
    ptype = 1

    @sensitive_variables("data", "request")
    @classmethod
    def auth_test(cls, request, data, **kwargs):
        if request.POST.get("password", "") in data["passwords"]:
            return True
        else:
            return False
    @classmethod
    def auth_render(cls, **kwargs):
        return TemplateResponse()

    def __str__(self):
        return _("Password based authentication")

#@add_protection
class AuditPasswordProtection(BaseProtection):
    name = "auditpw"
    ptype = 1

    @sensitive_variables("data", "request")
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
    #@add_protection
    class JWTProtection(BaseProtection):
        name = "jwt"
        ptype = 0
        def validate(self, request, data, **kwargs):
            if request.user.username in data.get("users", []):
                return True
            else:
                return False

        def render(self, request, obj, **kwargs):
            return redirect_to_login(redirect(obj), settings.LOGIN_URL, REDIRECT_FIELD_NAME)

        def __str__(self):
            return _("JWT Authentification")
