from django.contrib.auth.backends import ModelBackend

from .models import UserComponent, Protection
from .protections import ProtectionType


def set_generic_protections(request, protection_codes):
    request.protections = Protection.authall(
        request, scope="auth", ptype=ProtectionType.authentication.value,
        protection_codes=protection_codes
    )


class SpiderAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, nospider=False, **kwargs):
        """ Use protections for authentication"""
        # disable SpiderAuthBackend backend (against recursion)
        if nospider:
            return
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()
        if not uc:
            set_generic_protections(request, protection_codes)
        else:
            request.protections = uc.auth(
                request, scope="auth",
                ptype=ProtectionType.authentication.value,
                protection_codes=protection_codes, **kwargs
            )
            if request.protections is True:
                return uc.user
