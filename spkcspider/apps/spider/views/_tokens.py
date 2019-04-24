__all__ = (
    "TokenDelete", "TokenDeletionRequest", "TokenRenewal"
)

import logging

from django.shortcuts import get_object_or_404
from django.views.generic.edit import DeleteView
from django.http import (
    Http404, HttpResponseServerError, JsonResponse, HttpResponseRedirect,
    HttpResponse
)

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

import requests
import certifi

from ._core import UCTestMixin
from ..models import AuthToken
from ..helpers import get_settings_func
from ..constants import TokenCreationError


class TokenDelete(UCTestMixin, DeleteView):

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
                    "expires": None if i.persist >= 0 else (
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
        if self.has_special_access(
            user_by_token=True, user_by_login=True,
            superuser=True, staff="spider_base.delete_authtoken"
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
            persist__gte=0
        )

    def delete(self, request, *args, **kwargs):
        self.object.delete()
        return HttpResponseRedirect(
            redirect_to=self.object.referrer
        )

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class TokenRenewal(UCTestMixin, View):
    model = AuthToken

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_usercomponent(self):
        token = self.request.POST.get("token", None)
        if not token:
            raise Http404()
        self.request.auth_token = get_object_or_404(
            AuthToken,
            token=token,
            persist__gte=0,
            referrer__isnull=False
        )
        if (
            not self.request.auth_token.referrer or
            "persist" not in self.request.auth_token.extra.get(
                "intentions", []
            )
        ):
            raise Http404()
        return self.request.auth_token.usercomponent

    def test_func(self):
        return True

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def update_with_post(self):
        # application/x-www-form-urlencoded is best here,
        # for beeing compatible to most webservers
        # client side rdf is no problem
        # NOTE: csrf must be disabled or use csrf token from GET,
        #       here is no way to know the token value
        try:
            d = {
                "token": self.request.auth_token.token,
                "renew": "true"
            }
            if "payload" in self.request.POST:
                d["payload"] = self.request.POST["payload"]
            ret = requests.post(
                self.request.auth_token.referrer,
                data=d,
                headers={
                    "Referer": "%s://%s" % (
                        self.request.scheme,
                        self.request.path
                    )
                },
                timeout=settings.SPIDER_REQUESTS_TIMEOUT,
                verify=certifi.where()
            )
            ret.raise_for_status()
        except requests.exceptions.SSLError as exc:
            logging.info(
                "referrer: \"%s\" has a broken ssl configuration",
                self.request.auth_token.referrer, exc_info=exc
            )
            return False
        except Exception as exc:
            logging.info(
                "post failed: \"%s\" failed",
                self.request.auth_token.referrer, exc_info=exc
            )
            return False
        return True

    def post(self, request, *args, **kwargs):
        self.request.auth_token.create_token()
        success = True
        if "sl" in self.request.extra.get("intentions", []):
            # only the original referer can access this
            success = (
                self.request["Referer"] == self.request.auth_token.referrer
            )
        else:
            # if not serverless:
            # you cannot steal a token because it is bound to a domain
            # damage can be only done in persisted data
            success = self.update_with_post()
        if success:
            try:
                self.request.auth_token.save()
            except TokenCreationError:
                success = False
        if not success:
            logging.exception("Token creation failed")
            return HttpResponseServerError(
                "Token update failed, try again"
            )
        if "sl" in self.request.extra.get("intentions", []):
            ret = HttpResponse(
                self.request.auth_token.token.encode(
                    "ascii"
                ), content_type="text/plain"
            )
            ret["Access-Control-Allow-Origin"] = \
                self.request.auth_token.referrer
        else:
            ret = HttpResponse(status_code=200)
        # no sl: simplifies update logic for thirdparty web servers
        # sl: safety (but anyway checked by referer check)
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret
