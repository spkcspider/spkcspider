__all__ = ["ReferrerMixin"]


import hashlib
import logging
from urllib.parse import quote_plus

import requests

import ratelimit
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.db import transaction
from django.db.models import Q
from django.forms.widgets import Media
from django.http import (
    HttpResponse, HttpResponseRedirect, HttpResponseServerError
)
from django.test import Client
from django.utils.translation import gettext
from spkcspider.constants import TokenCreationError
from spkcspider.utils.security import get_hashob
from spkcspider.utils.settings import get_settings_func
from spkcspider.utils.urls import merge_get_url

from ..conf import VALID_INTENTIONS, VALID_SUB_INTENTIONS, get_requests_params
from ..models import AuthToken, ReferrerObject

logger = logging.getLogger(__name__)
_extra = '' if settings.DEBUG else '.min'


class ReferrerMixin(object):
    allow_domain_mode = False

    def get_context_data(self, **kwargs):
        kwargs["token_strength"] = None
        # will be overwritten in referring path so there is no interference
        kwargs["referrer"] = None
        kwargs["intentions"] = set()
        if self.request.auth_token:
            kwargs["referrer"] = self.request.auth_token.referrer
            kwargs["token_strength"] = self.request.auth_token.extra.get(
                "strength", None
            )
            kwargs["intentions"].update(self.request.auth_token.extra.get(
                "intentions", []
            ))
        return super().get_context_data(**kwargs)

    def test_token(self, minstrength, force_token=False, taint=False):
        if "intention" in self.request.GET or "referrer" in self.request.GET:
            # validate early, before auth
            intentions = set(self.request.GET.getlist("intention"))
            if not VALID_INTENTIONS.issuperset(
                intentions
            ):
                return HttpResponse(
                    "invalid intentions", status=400
                )
            if "domain" in intentions:

                if not self.clean_domain_upgrade(
                    {"intentions": intentions},
                    False
                ):
                    return HttpResponse(
                        "invalid domain upgrade", status=400
                    )
                # requires token
                force_token = True
            else:
                # can be either domain or auth to not have taint flag
                if "auth" not in intentions:
                    taint = True
                # maximal one main intention
                if len(intentions.difference(VALID_SUB_INTENTIONS)) > 1:
                    return HttpResponse(
                        "invalid intentions", status=400
                    )
                minstrength = 4
        return super().test_token(minstrength, force_token, taint)

    def refer_with_post(self, context, token):
        # application/x-www-form-urlencoded is best here,
        # for beeing compatible to most webservers
        # client side rdf is no problem
        # NOTE: csrf must be disabled or use csrf token from GET,
        #       here is no way to know the token value

        h = hashlib.sha256(context["referrer"].encode("utf8")).hexdigest()

        def h_fun(*a):
            return h
        # rate limit on errors
        if ratelimit.get_ratelimit(
            request=self.request,
            group="refer_with_post.refer_with_post",
            key=h_fun,
            rate=settings.SPIDER_DOMAIN_ERROR_RATE,
            inc=False
        )["request_limit"] > 0:
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    status="post_failed",
                    error="error_rate_limit"
                )
            )
        d = {
            "token": token.token,
            "hash_algorithm": settings.SPIDER_HASH_ALGORITHM.name,
            "action": context["action"],
        }
        if context["payload"] is not None:
            d["payload"] = context["payload"]
        params, inline_domain = get_requests_params(context["referrer"])
        if inline_domain:
            response = Client().post(
                context["referrer"],
                data=d,
                Connection="close",
                Referer=merge_get_url(
                    "%s%s" % (
                        context["hostpart"],
                        self.request.path
                    )
                    # sending full url not required anymore, payload
                ),
                SERVER_NAME=inline_domain
            )
            if response.status_code != 200:
                return HttpResponseRedirect(
                    redirect_to=merge_get_url(
                        context["referrer"],
                        status="post_failed",
                        error="other"
                    )
                )
        else:
            try:
                with requests.post(
                    context["referrer"],
                    data=d,
                    headers={
                        "Referer": merge_get_url(
                            "%s%s" % (
                                context["hostpart"],
                                self.request.path
                            )
                            # sending full url not required anymore, payload
                        ),
                        "Connection": "close"
                    },
                    **params
                ) as resp:
                    resp.raise_for_status()
            except requests.exceptions.SSLError as exc:
                logger.info(
                    "referrer: \"%s\" has a broken ssl configuration",
                    context["referrer"], exc_info=exc
                )
                return HttpResponseRedirect(
                    redirect_to=merge_get_url(
                        context["referrer"],
                        status="post_failed",
                        error="ssl"
                    )
                )
            except (Exception, requests.exceptions.HTTPError) as exc:
                apply_error_limit = False
                if isinstance(
                    exc, (
                        requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout
                    )
                ):
                    apply_error_limit = True
                elif (
                    isinstance(exc, requests.exceptions.HTTPError) and
                    exc.response.status_code >= 500
                ):
                    apply_error_limit = True
                if apply_error_limit:
                    ratelimit.get_ratelimit(
                        request=self.request,
                        group="refer_with_post",
                        key=h_fun,
                        rate=settings.SPIDER_DOMAIN_ERROR_RATE,
                        inc=True
                    )
                logger.info(
                    "post failed: \"%s\" failed",
                    context["referrer"], exc_info=exc
                )
                return HttpResponseRedirect(
                    redirect_to=merge_get_url(
                        context["referrer"],
                        status="post_failed",
                        error="other"
                    )
                )
        context["post_success"] = True
        h = get_hashob()
        h.update(token.token.encode("utf-8", "ignore"))
        return HttpResponseRedirect(
            redirect_to=merge_get_url(
                context["referrer"],
                status="success",
                hash=h.finalize().hex()
            )
        )

    def refer_with_get(self, context, token):
        return HttpResponseRedirect(
            redirect_to=merge_get_url(
                context["referrer"],
                token=token.token,
                payload=context["payload"]
            )
        )

    def clean_domain_upgrade(self, context, token):
        if "referrer" not in self.request.GET:
            return False
        # domain mode must be used alone
        if len(context["intentions"]) > 1:
            return False
        if not context["intentions"].issubset(VALID_INTENTIONS):
            return False

        if not getattr(self.request, "_clean_domain_upgrade_checked", False):
            if ratelimit.get_ratelimit(
                request=self.request,
                group="clean_domain_upgrade",
                key=("get", {"IP": True, "USER": True}),
                rate=settings.SPIDER_DOMAIN_UPDATE_RATE,
                inc=True
            )["request_limit"] > 0:
                return False

            setattr(self.request, "_clean_domain_upgrade_checked", True)

        # False for really no token
        if token is False:
            return True
        if not token or token.extra.get("strength", 0) >= 10:
            return False
        return True

    def clean_refer_intentions(self, context, token=None):
        # Only owner can use other intentions than domain
        if not self.request.is_owner:
            return False
        # Second error: invalid intentions
        #  this is the second time the validation will be executed
        #    in case test_token path is used
        #  this is the first time the validation will be executed
        #    in case has_special_access path is used
        if not context["intentions"].issubset(VALID_INTENTIONS):
            return False

        # auth is only for self.requesting component auth
        if "auth" in context["intentions"]:
            return False
        # maximal one main intention
        if len(context["intentions"].difference(VALID_SUB_INTENTIONS)) > 1:
            return False
        # "persist" or default can be serverless other intentions not
        #  this way rogue client based attacks are prevented
        if "persist" in context["intentions"]:
            if not self.usercomponent.features.filter(
                name="Persistence"
            ).exists():
                return False
        else:
            if context["is_serverless"] and len(context["intentions"]) != 1:
                return False

        if not token:
            return True

        ####### with token ########  # noqa: 266E
        # cannot add sl intention to existing intentions
        if "sl" in context["intentions"].difference(
            token.extra.get("intentions", ["sl"])
        ):
            return False
        if "persist" in context["intentions"]:
            # set persist = true, (false=-1)
            token.persist = 0
            # if possible, pin to anchor
            if self.usercomponent.primary_anchor:
                token.persist = self.usercomponent.primary_anchor_id
        else:
            token.persist = -1

        if not token.extra.get("initial_referrer_url", None):
            token.extra["initial_referrer_url"] = "{}://{}{}".format(
                self.request.scheme,
                self.request.get_host(),
                self.request.path
            )
        return True

    def handle_domain_auth(self, context, token):
        assert token or self.request.is_special_user, \
            "special user and no token"

        context.setdefault("payload", None)
        context.setdefault("action", "create")
        if not self.allow_domain_mode:
            return HttpResponse(
                status=400,
                content='domain mode disallowed'
            )
        if not self.clean_domain_upgrade(context, token):
            return HttpResponse(
                status=400,
                content='Invalid token'
            )
        token.initialize_token()
        token.referrer = ReferrerObject.objects.get_or_create(
            url=context["referrer"]
        )[0]
        token.extra["intentions"] = list(context["intentions"])
        try:
            token.save()
        except TokenCreationError:
            logger.exception("Token creation failed")
            return HttpResponseServerError(
                "Token creation failed, try again"
            )
        context["post_success"] = False
        ret = self.refer_with_post(context, token)
        if not context["post_success"]:
            token.delete()
        return ret

    def handle_referrer_request(
        self, context, token, keep=False, dontact=False, no_oldtoken=False
    ):
        """
            no_oldtoken: don't use old token for calculating:
                           old_ids, old_search
                         (performance and manual old_* possible)
            dontact: dont act if probing results fails
        """
        _ = gettext
        context.setdefault("action", "create")
        context.setdefault("model", self.model)
        context.setdefault("payload", None)
        context.setdefault("ids", set())
        context.setdefault("filter", set())
        context.setdefault("old_ids", set())
        context.setdefault("old_search", set())
        context["is_serverless"] = "sl" in context["intentions"]
        if keep is True:
            context["ids"].update(token.extra.get("ids", []))
            context["search"].update(token.extra.get("filter", []))

        action = self.request.POST.get("action", None)
        if context["action"].endswith("invalid"):
            action = context["action"]
        if action == "confirm":
            newtoken = None
            # if persist try to find old token
            if "persist" in context["intentions"]:
                oldtoken = AuthToken.objects.filter(
                    Q(persist__gte=0, usercomponent=token.usercomponent),
                    referrer__url=context["referrer"]
                ).first()
                if oldtoken:
                    newtoken = token
                    token = oldtoken
            # either reuse persistent token with auth token tokenstring
            # or just reuse auth token
            if newtoken:
                # steal token value
                token.token = newtoken.token

            # set to zero as prot_strength can elevate perms
            token.extra["taint"] = False
            token.extra["prot_strength"] = 0
            token.extra["intentions"] = list(context["intentions"])
            token.extra.pop("request_referrer", None)
            token.extra.pop("request_intentions", None)
            token.extra.pop("request_search", None)

            if not self.clean_refer_intentions(context, token):
                return HttpResponseRedirect(
                    redirect_to=merge_get_url(
                        context["referrer"],
                        error="intentions_incorrect"
                    )
                )

            token.extra["search"] = list(context["search"])
            if "live" in context["intentions"]:
                token.extra.pop("ids", None)
            else:
                token.extra["ids"] = list(context["ids"])
            token.referrer = ReferrerObject.objects.get_or_create(
                url=context["referrer"]
            )[0]
            # after cleanup, save
            try:
                with transaction.atomic():
                    # must be done here, elsewise other token can (unlikely)
                    # take token as it is free for a short time, better be safe
                    if newtoken:
                        newtoken.delete()
                    token.save()
            except TokenCreationError:
                logger.exception("Token creation failed")
                return HttpResponseServerError(
                    _("Token creation failed, try again")
                )

            if context["is_serverless"]:
                context["post_success"] = True
                ret = self.refer_with_get(context, token)
            else:
                context["post_success"] = False
                ret = self.refer_with_post(context, token)
            if dontact:
                return ret
            if not context["post_success"]:
                if newtoken:
                    logger.warning(
                        "Updating persisting token failed"
                    )
                else:
                    token.delete()
            return ret

        elif action == "cancel":
            if not dontact:
                token.delete()
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    status="canceled",
                    payload=context["payload"]
                )
            )
        else:
            if (
                no_oldtoken and
                "persist" in context["intentions"]
            ):
                oldtoken = AuthToken.objects.filter(
                    Q(persist__gte=0, usercomponent=token.usercomponent),
                    referrer__url=context["referrer"],
                ).first()

                if oldtoken:
                    context["old_ids"].update(oldtoken.extra.get("ids", []))
                    context["old_search"].update(oldtoken.extra.get(
                        "filter", []
                    ))

            if not self.clean_refer_intentions(context, token):
                return HttpResponse(
                    status=400,
                    content=_('Error: intentions incorrect')
                )
            context["object_list"] = context["model"].objects.filter(
                id__in=context["ids"]
            )
            # remove other media
            context["media"] = Media(
                css={
                    "all": [
                        'node_modules/@devkral/selectize/dist/css/selectize.default.css'  # noqa:E501
                    ]
                },
                js=[
                    'node_modules/jquery/dist/jquery%s.js' % _extra,
                    'node_modules/@devkral/selectize/dist/js/standalone/selectize%s.js' % _extra  # noqa: E501
                ]
            )
            return self.response_class(
                request=self.request,
                template=self.get_referrer_template_names(),
                context=context,
                using=self.template_engine,
                content_type=self.content_type
            )

    def handle_referrer(self):
        _ = gettext
        if (
            self.request.user != self.usercomponent.user and
            not self.request.auth_token
        ):
            if self.request.user.is_authenticated:
                return self.handle_no_permission()
            return HttpResponseRedirect(
                redirect_to="{}?{}={}".format(
                    self.get_login_url(),
                    REDIRECT_FIELD_NAME,
                    quote_plus(
                        merge_get_url(
                            self.request.build_absolute_uri(),
                            token=None
                        )
                    )
                )
            )

        context = self.get_context_data()
        context["action"] = "create"
        context["intentions"] = set(self.request.GET.getlist("intention"))
        if "referrer" in self.request.POST:
            context["referrer"] = merge_get_url(self.request.POST["referrer"])
            if not get_settings_func(
                "SPIDER_URL_VALIDATOR",
                "spkcspider.apps.spider.functions.validate_url_default"
            )(context["referrer"], self):
                context["action"] = "referrer_invalid"
        else:
            context["referrer"] = merge_get_url(self.request.GET["referrer"])
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
        context["payload"] = self.request.GET.get("payload", None)
        token = self.request.auth_token
        if not token:
            token = AuthToken(
                usercomponent=self.usercomponent,
                extra={
                    "strength": 10,
                    "taint": False
                }
            )
        if "domain" in context["intentions"]:
            return self.handle_domain_auth(context, token)
        else:
            context["ids"] = set(self.object_list.values_list("id", flat=True))
            context["search"] = set(self.request.POST.getlist("search"))
            return self.handle_referrer_request(
                context, token
            )

    def get_referrer_template_names(self):
        return "spider_base/protections/referring.html"
