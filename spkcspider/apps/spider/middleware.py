__all__ = ["TokenUserMiddleware"]

from django.utils import timezone


from .models import AuthToken


class TokenUserMiddleware(object):

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
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
                    return self.get_response(request)
                request.user = uc.user
                request._cached_user = uc.user
        return self.get_response(request)
