
from .models import UserComponent
# from .protections import ProtectionType


class SpiderAuthBackend(object):

    def authenticate(self, request, username=None, password=None):
        if not username:
            return
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()
        if not uc:
            return
        request.auth_results = uc.authenticate(request, "auth")
        if request.auth_results is True:
            request.auth_results = None
            return uc.user
