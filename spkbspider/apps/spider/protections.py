"""
installed_protections, add_protection
namespace: spiderucs

"""

__all__ = ["add_protection", "ProtectionType", "check_blacklisted", "installed_protections", "BaseProtection"]

import enum

from django.conf import settings
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from django.views.decorators.debug import sensitive_variables


try:
    import jwt
except ImportError:
    jwt = None


installed_protections = {}

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

class ProtectionType(enum.IntEnum):
    access_control = 0
    authentication = 1
    recovery = 2

# form with inner form for authentication
class BaseProtection(forms.Form):
    active = forms.BooleanField(required=True)

    # ptype= 0: access control, 1: authentication, 2: recovery
    # 1, 2 require render
    ptype = ProtectionType.access_control

    template_name = None
    template_engine = None
    response_class = TemplateResponse
    content_type = None

    # auto populated, instance
    protection = None
    assigned = None

    def __init__(self, *args, assigned=None, **kwargs):
        self.protection = kwargs.pop("protection")
        initial = None
        if assigned:
            initial = assigned.filter(protection=self.protection).first()
        if initial:
            initial = initial.protectiondata
        super().__init__(*args, initial=initial, **kwargs)

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
    ptype = ProtectionType.access_control

    @classmethod
    def auth_test(cls, _request, _data, **kwargs):
        return True
    def __str__(self):
        return _("Allow")


#def friend_query():
#    return get_user_model().objects.filter(active=True)

# only friends have access
#@add_protection
#class FriendProtection(BaseProtection):
#    name = "friends"
#    users = forms.ModelMultipleChoiceField(queryset=friend_query())
#    ptype = ProtectionType.access_control
#    @classmethod
#    def auth_test(cls, request, data, **kwargs):
#        if request.user.id in data["users"]:
#            return True
#        else:
#            return False
#
#    def __str__(self):
#        return _("Friends")

#@add_protection
class PasswordProtection(BaseProtection):
    name = "pw"
    ptype = ProtectionType.authentication

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
