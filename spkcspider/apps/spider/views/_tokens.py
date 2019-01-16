__all__ = (
    "TokenDelete", "TokenDeletionRequest"
)

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic.edit import DeleteView
from django.http import JsonResponse, HttpResponseRedirect

from ._core import UCTestMixin, EntityDeletionMixin
from ..models import AuthToken
from ..helpers import get_settings_func

class TokenDelete(UCTestMixin, DeleteView):
    no_nonce_usercomponent = True
    also_authenticated_users = True

    def get_object(self):
        return None

    def delete(self, request, *args, **kwargs):
        self.remove_old_tokens()
        query = AuthToken.objects.filter(
            usercomponent=self.usercomponent,
            id__in=self.request.POST.getlist("tokens")
        )
        # replace active admin token
        if query.filter(
            created_by_special_user=self.request.user
        ).exists():
            self.request.auth_token = self.create_token(
                self.request.user,
                extra={
                    "strength": 10
                }
            )
        query.delete()
        del query
        return self.get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.delete(self, request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.remove_old_tokens()
        response = {
            "tokens": [
                {
                    "expires": None if i.persist else (
                        i.created +
                        self.usercomponent.token_duration
                    ).strftime("%a, %d %b %Y %H:%M:%S %z"),
                    "referrer": i.referrer if i.referrer else "",
                    "name": str(i),
                    "id": i.id
                } for i in AuthToken.objects.filter(
                    usercomponent=self.usercomponent
                )
            ],
            "admin": AuthToken.objects.filter(
                usercomponent=self.usercomponent,
                created_by_special_user=self.request.user
            ).first()
        }
        if response["admin"]:
            # don't censor, required in modal presenter
            response["admin"] = response["admin"].token
        return JsonResponse(response)


class TokenDeletionRequest(UCTestMixin, DeleteView):
    no_nonce_usercomponent = True
    also_authenticated_users = True
    model = AuthToken
    template_name = "spider_base/protections/authtoken_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def test_func(self):
        staff_perm = "spider_base.delete_authtoken"
        if self.has_special_access(
            staff=True, superuser=True, staff_perm=staff_perm
        ):
            return True
        return self.test_token()

    def get_usercomponent(self):
        return self.object.usercomponent

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()

        return get_object_or_404(
            queryset,
            token=self.request.GET.get("delete", ""),
            persist=True
        )

    def delete(self, request, *args, **kwargs):
        self.object.delete()
        return HttpResponseRedirect(
            redirect_to=self.object.referrer
        )

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
