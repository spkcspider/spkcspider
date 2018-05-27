
from .models import UserComponent, Protection
from .protections import ProtectionType


def set_generic_protections(request):
    request.protections = Protection.authall(
        request, scope="auth", ptype=ProtectionType.authentication
    )


class SpiderAuthBackend(object):

    def authenticate(self, request, username=None, password=None):
        if not username:
            set_generic_protections(request)
            return
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()
        if not uc:
            set_generic_protections(request)
            return
        request.protections = uc.auth(
            request, scope="auth", ptype=ProtectionType.authentication,
            password=password
        )
        if request.protections is True:
            return uc.user
