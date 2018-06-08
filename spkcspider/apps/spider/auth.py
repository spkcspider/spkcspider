from django.contrib.auth.backends import ModelBackend

from .models import UserComponent, Protection
from .protections import ProtectionType


class SpiderAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, nospider=False,
                     autocreate_login=True, **kwargs):
        """ Use protections for authentication"""
        # disable SpiderAuthBackend backend (against recursion)
        if nospider:
            return
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()
        if not uc:
            request.protections = Protection.authall(
                request, scope="auth",
                ptype=ProtectionType.authentication.value,
                protection_codes=protection_codes
            )
        else:
            request.protections = uc.auth(
                request, scope="auth",
                ptype=ProtectionType.authentication.value,
                protection_codes=protection_codes
            )
            if request.protections is True:
                return uc.user
