__all__ = ["TokenUserMiddleware"]

from django.utils import timezone
from django.utils.functional import SimpleLazyObject

from .models import AuthToken


def get_user(request):
    # check for admin auth token
    token = request.headers.get("X-TOKEN", None)
    if token:
        now = timezone.now()

        token = AuthToken.objects.filter(
            usercomponent__name="index",
            token=token
        ).first()
        if token:
            uc = token.usercomponent
            if (
                # token.persist == -1 and  # cannot persist
                token.created < now - uc.token_duration
            ):
                token.delete()
                return None
            return uc.user
    return None


def get_cached_user(request):
    if not hasattr(request, "_cached_spidertoken_user"):
        request._cached_spidertoken_user = get_user(request)
    return request._cached_spidertoken_user


class TokenUserMiddleware(object):
    """ should come after AuthenticationMiddleware """
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        if hasattr(request, "user"):
            user = request.user
            request.user = SimpleLazyObject(
                lambda: get_cached_user(request) or user
            )
        else:
            request.user = SimpleLazyObject(
                lambda: get_cached_user(request)
            )
        return self.get_response(request)
