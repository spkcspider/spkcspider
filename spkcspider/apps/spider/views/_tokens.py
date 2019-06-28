__all__ = (
    "AdminTokenManagement", "TokenDeletionRequest", "TokenRenewal",
    "ConfirmTokenUpdate", "RequestTokenUpdate"
)

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.views.generic.base import View, TemplateView
from django.views.generic.edit import DeleteView
from django.utils.translation import gettext

from django.http import (
    Http404, HttpResponseServerError, JsonResponse, HttpResponseRedirect,
    HttpResponse
)

from django.utils.http import is_safe_url
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.test import Client


import requests

from ._core import UCTestMixin, UserTestMixin
from ._referrer import ReferrerMixin
from ..models import AuthToken
from ..helpers import get_settings_func, get_requests_params, merge_get_url
from ..constants import TokenCreationError


logger = logging.getLogger(__name__)


class AdminTokenManagement(UCTestMixin, View):
    scope = None
    created_token = None

    def dispatch_extra(self, request, *args, **kwargs):
        self.remove_old_tokens()

    def test_func(self):
        if self.scope == "delete":
            return self.has_special_access(
                user_by_login=True
            )
        else:
            return self.has_special_access(
                user_by_login=True, user_by_token=True
            )

    def post(self, request, *args, **kwargs):
        if self.request.POST.get("add_token"):
            extra = {
                "strength": self.usercomponent.strength,
            }
            if self.request.POST.get("restrict"):
                extra["ids"] = [-1]
            elif self.request.GET.get("id", "") != "":
                try:
                    extra["ids"] = list(set(map(
                        int, self.request.GET.getlist("id")
                    )))
                except Exception:
                    return HttpResponse(status=400)
            if self.request.GET.get("search", "") != "":
                extra["search"] = list(set(
                    self.request.GET.getlist("search")
                ))
            self.created_token = self.create_token(
                extra=extra
            )

        try:
            delids = set(map(int, self.request.POST.getlist("delete_tokens")))
        except Exception:
            return HttpResponse(status=400)
        if delids:
            delquery = AuthToken.objects.filter(
                usercomponent=self.usercomponent,
                id__in=delids
            )
            if self.scope == "share":
                delquery = delquery.filter(
                    Q(session_key=request.session.session_key) |
                    Q(token=request.auth_token)
                )
            shall_redirect = delquery.filter(token=request.auth_token).exists()
            delquery.delete()
            del delquery
            if shall_redirect:
                return HttpResponseRedirect(
                    redirect_to=request.get_full_path()
                )

        return self.get(request, *args, **kwargs)

    def _token_dict(self, token):
        # sl or not initialized map to full
        full = "sl" in token.extra.get("intentions", ["sl"])
        ret = {
            "admin_key": token.extra.get("prot_strength", 0) >= 4,
            "created": self.created_token == token,
            "restricted": token.extra.get("ids", []) == [-1],
            "expires": None if token.persist >= 0 else (
                token.created +
                self.usercomponent.token_duration
            ).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "referrer": token.referrer.url if token.referrer else "",
            "token": token.token if full else None,
            "name": str(token),
            "id": token.id,
            "needs_confirmation": (
                token.extra.get("request_intentions") is not None or
                token.extra.get("request_search") is not None or
                token.extra.get("request_referrer") is not None
            )
        }
        if token.session_key == self.request.session.session_key:
            assert(not token.referrer)
            ret["same_session"] = True
        elif self.request.auth_token == token:
            assert(not token.referrer)
            ret["same_session"] = True
        else:
            ret["same_session"] = False

        return ret

    def get(self, request, *args, **kwargs):
        if self.scope == "delete":
            response = {
                "tokens": list(map(
                    self._token_dict,
                    AuthToken.objects.filter(
                        usercomponent=self.usercomponent
                    )
                )),
            }
        else:
            response = {
                "tokens": list(filter(
                    lambda x: x["token"], map(
                        self._token_dict,
                        AuthToken.objects.filter(
                            Q(session_key=request.session.session_key) |
                            Q(token=request.auth_token),
                            usercomponent=self.usercomponent,
                        )
                    )
                )),
            }
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
                "SPIDER_RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def test_func(self):
        # tokens which are not persistent can be easily deleted
        if self.object.persist < 0:
            return True
        if self.has_special_access(
            user_by_token=True, user_by_login=True,
            superuser=True, staff="spider_base.delete_authtoken"
        ):
            return True
        return False

    def get_usercomponent(self):
        return self.object.usercomponent

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()

        return get_object_or_404(
            queryset,
            token=self.request.GET.get("delete", ""),
        )

    def get(self, request, *args, **kwargs):
        # tokens which are not persistent can be easily deleted
        if self.object.persist < 0:
            return self.delete(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        url = None
        if self.object.referrer:
            url = self.object.referrer.url
        self.object.delete()
        if not url:
            return HttpResponse(status=200)
        return HttpResponseRedirect(
            redirect_to=url
        )

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = "*"
        ret["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        return ret


class TokenRenewal(UCTestMixin, View):
    model = AuthToken
    oldtoken = None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
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
        assert (
            "persist" in self.request.auth_token.extra.get(
                "intentions", []
            )
        )
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
        d = {
            "oldtoken": self.oldtoken,
            "token": self.request.auth_token.token,
            "hash_algorithm": settings.SPIDER_HASH_ALGORITHM.name,
            "action": "renew"
        }
        if "payload" in self.request.POST:
            d["payload"] = self.request.POST["payload"]

        params, can_inline = get_requests_params(
            self.request.auth_token.referrer.url
        )
        if can_inline:
            response = Client().post(
                self.request.auth_token.referrer.url,
                data=d,
                Connection="close",
                Referer="%s://%s" % (
                    self.request.scheme,
                    self.request.path
                )
            )
            if response.status_code >= 400:
                return False
        else:
            try:
                with requests.post(
                    self.request.auth_token.referrer.url,
                    data=d,
                    headers={
                        "Referer": "%s://%s" % (
                            self.request.scheme,
                            self.request.path
                        ),
                        "Connection": "close"
                    },
                    **params
                ) as resp:
                    resp.raise_for_status()
            except requests.exceptions.SSLError as exc:
                logger.info(
                    "referrer: \"%s\" has a broken ssl configuration",
                    self.request.auth_token.referrer, exc_info=exc
                )
                return False
            except Exception as exc:
                logger.info(
                    "post failed: \"%s\" failed",
                    self.request.auth_token.referrer, exc_info=exc
                )
                return False
        return True

    def post(self, request, *args, **kwargs):
        self.oldtoken = self.request.auth_token.token
        self.request.auth_token.initialize_token()
        success = True
        sl = "sl" in self.request.auth_token.extra.get("intentions", [])
        if sl:
            # only the original referer can access this
            success = (
                self.request.headers.get("Referer", "").startswith(
                    self.request.auth_token.referrer.url
                )
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
            logger.exception("Token creation failed")
            return HttpResponseServerError(
                "Token update failed, try again"
            )
        if sl:
            ret = HttpResponse(
                self.request.auth_token.token.encode(
                    "ascii"
                ),
                content_type="text/plain",
                status=200
            )
        else:
            ret = HttpResponse(status=200)
        # no sl: simplifies update logic for thirdparty web servers
        # sl: safety (but anyway checked by referer check)
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret


class ConfirmTokenUpdate(ReferrerMixin, UCTestMixin, TemplateView):
    model = AuthToken
    redirect_field_name = "next"
    preserved_GET_parameters = {"token", "page", "search", "id", "protection"}

    def get_redirect_url(self, sanitized_GET=None):
        """Return the user-originating redirect URL if it's safe."""
        if not sanitized_GET:
            sanitized_GET = self.sanitize_GET()
        redirect_to = self.request.GET.get(
            self.redirect_field_name,
            self.request.GET.get(self.redirect_field_name, '')
        )
        url_is_safe = is_safe_url(
            url=redirect_to,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )
        redirect_to = "{}?{}".format(
            url_is_safe.rstrip("?&"),
            sanitized_GET
        )

        return redirect_to if url_is_safe else ''

    def test_func(self):
        return self.has_special_access(
            user_by_login=True, user_by_token=True
        )

    def dispatch_extra(self, request, *args, **kwargs):
        _ = gettext
        context = self.get_context_data()
        # fallback to intentions if no request_intentions
        # remove "domain", "sl"
        context["intentions"] = set(self.object.extra.get(
            "request_intentions", self.object.extra.get(
                "intentions", []
            )
        ))
        # sl or domain should NOT be allowed for token updates
        # sl is only for clients, domain only initial and should be removed
        context["intentions"].difference_update({"domain", "sl"})
        context["action"] = "update"
        context["uc"] = self.object.usercomponent

        rreferrer = request.POST.get("referrer", None)
        if rreferrer:
            context["referrer"] = merge_get_url(rreferrer)
            if not get_settings_func(
                "SPIDER_URL_VALIDATOR",
                "spkcspider.apps.spider.functions.validate_url_default"
            )(context["referrer"], self):
                context["action"] = "referrer_invalid"
            # for donotact
            if self.object.referrer and self.object.referrer.url == rreferrer:
                rreferrer = None
        else:
            rreferrer = self.object.extra.get("request_referrer", None)
            if rreferrer:
                context["referrer"] = merge_get_url(rreferrer)
                if not get_settings_func(
                    "SPIDER_URL_VALIDATOR",
                    "spkcspider.apps.spider.functions.validate_url_default"
                )(context["referrer"], self):
                    return HttpResponse(
                        status=400,
                        content=_('Insecure url: %(url)s') % {
                            "url": context["referrer"]
                        }
                    )
            elif self.object.referrer:
                context["referrer"] = self.object.referrer.url
            else:
                context["referrer"] = ""
        context["ids"] = self.object.usercomponent.contents.values_list(
            "id", flat=True
        )
        context["ids"] = set(context["ids"])
        # if requested referrer is available DO delete invalid and DO care
        ret = self.handle_referrer_request(
            context, self.object, dontact=not rreferrer, no_oldtoken=True
        )
        if isinstance(ret, HttpResponseRedirect):
            if context.get("post_success", False):
                messages.success(request, _("Intention update successful"))
            else:
                messages.error(request, _("Intention update failed"))
            return HttpResponseRedirect(self.get_redirect_url(
                context["sanitized_GET"]
            ))
        return ret

    def get_usercomponent(self):
        self.object = get_object_or_404(
            AuthToken,
            id=self.request.GET.get("refid", None),
        )
        return self.object.usercomponent


class RequestTokenUpdate(UserTestMixin, View):

    def test_func(self):
        self.request.auth_token = get_object_or_404(
            AuthToken,
            token=self.request.POST("token"),
        )
        return bool(self.request.auth_token)

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get(self, request, *args, **kwargs):
        ret_dict = {
            "intentions": request.auth_token.extra.get("intentions") or [],
            "search": request.auth_token.extra.get("search") or [],
            "referrer": None
        }
        if request.auth_token.referrer:
            ret_dict["referrer"] = request.auth_token.referrer.url
        if request.auth_token.extra.get("request_referrer") is not None:
            ret_dict["referrer"] = \
                request.auth_token.extra["request_referrer"]
        if request.auth_token.extra.get("request_intentions") is not None:
            ret_dict["intentions"] = \
                request.auth_token.extra["request_intentions"]
        if request.auth_token.extra.get("request_search") is not None:
            ret_dict["search"] = request.auth_token.extra["request_search"]
        return JsonResponse(ret_dict)

    def post(self, request, *args, **kwargs):
        if "referrer" in request.POST:
            # will be checked a second time
            request.auth_token.extra["request_referrer"] = \
                request.POST.get("referrer")
        elif not request.auth_token.referrer:
            return HttpResponse("no referrer", status=400)
        if request.POST.get("intentions", "") != "":
            # will be checked a second time
            request.auth_token.extra["request_intentions"] = \
                request.POST.getlist("intentions")
        if request.POST.get("search", "") != "":
            # will be checked a second time
            request.auth_token.extra["request_search"] = \
                request.POST.getlist("search")
        request.auth_token.save(update_fields=["extra"])
        return self.get(request, *args, **kwargs)

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret
