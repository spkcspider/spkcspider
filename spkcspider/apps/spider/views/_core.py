__all__ = (
    "UserTestMixin", "UCTestMixin", "EntityDeletionMixin", "ReferrerMixin"
)

import hashlib
import logging
from urllib.parse import quote_plus

from datetime import timedelta

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.http import (
    HttpResponseRedirect, HttpResponseServerError, HttpResponse
)
from django.http.response import HttpResponseBase
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext

import ratelimit

import requests

from ..helpers import (
    merge_get_url, get_requests_params, get_settings_func, get_hashob
)
from ..constants import VariantType, TokenCreationError, ProtectionType
from ..conf import VALID_INTENTIONS, VALID_SUB_INTENTIONS
from ..models import UserComponent, AuthToken, ReferrerObject, TravelProtection


class UserTestMixin(AccessMixin):
    preserved_GET_parameters = set(["token", "protection"])
    login_url = reverse_lazy(getattr(
        settings,
        "LOGIN_URL",
        "auth:login"
    ))
    _travel_request = None

    def dispatch_extra(self, request, *args, **kwargs):
        return None

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
        self.request.is_owner = getattr(self.request, "is_owner", False)
        self.request.is_special_user = \
            getattr(self.request, "is_special_user", False)
        self.request.is_staff = getattr(self.request, "is_staff", False)
        self.request.auth_token = getattr(self.request, "auth_token", None)
        try:
            user_test_result = self.test_func()
        except TokenCreationError:
            logging.exception("Token creation failed")
            return HttpResponseServerError(
                _("Token creation failed, try again")
            )
        if isinstance(user_test_result, HttpResponseBase):
            return user_test_result
        elif not user_test_result:
            return self.handle_no_permission()

        ret = self.dispatch_extra(request, *args, **kwargs)
        if ret:
            return ret
        return super().dispatch(request, *args, **kwargs)

    def sanitize_GET(self):
        GET = self.request.GET.copy()
        for key in list(GET.keys()):
            if key not in self.preserved_GET_parameters:
                GET.pop(key, None)
        return GET

    def get_travel_for_request(self):
        if self._travel_request is None:
            self._travel_request = \
                TravelProtection.objects.get_active_for_request(self.request)
        return self._travel_request

    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = VariantType.raw_update.value
        kwargs["feature_type"] = VariantType.component_feature.value
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        kwargs["spider_GET"] = self.sanitize_GET()
        return super().get_context_data(**kwargs)

    # by default only owner with login can access view
    def test_func(self):
        return self.has_special_access(
            user_by_login=True
        )

    def replace_token(self):
        GET = self.request.GET.copy()
        GET["token"] = self.request.auth_token.token
        return HttpResponseRedirect(
            redirect_to="?".join((self.request.path, GET.urlencode()))
        )

    def create_token(self, extra=None):
        d = {
            "usercomponent": self.usercomponent,
            "session_key": None,
            "extra": {}
        }
        if "token" not in self.request.GET:
            d["session_key"] = self.request.session.session_key

        token = AuthToken(**d)
        # to copy dictionary
        if extra:
            token.extra.update(extra)
        token.save()
        return token

    def remove_old_tokens(self, expire=None):
        if not expire:
            expire = timezone.now()-self.usercomponent.token_duration
        return self.usercomponent.authtokens.filter(
            created__lt=expire, persist=-1
        ).delete()

    def test_token(self, minstrength=0, force_token=False):
        expire = timezone.now()-self.usercomponent.token_duration
        no_token = not force_token and self.usercomponent.required_passes == 0
        ptype = ProtectionType.access_control.value
        if minstrength >= 4:
            no_token = False
            ptype = ProtectionType.authentication.value

        # delete old token, so no confusion happen
        self.remove_old_tokens(expire)

        # only valid tokens here
        tokenstring = self.request.GET.get("token", None)
        token = None
        if tokenstring:
            # find by tokenstring
            token = self.usercomponent.authtokens.filter(
                token=tokenstring
            ).first()
        elif self.request.session.session_key:
            # use session_key
            token = self.usercomponent.authtokens.filter(
                session_key=self.request.session.session_key
            ).first()
        elif not no_token:
            # generate session key if it not exist and token is required
            self.request.session.cycle_key()
        if token and token.extra.get("prot_strength", 0) >= minstrength:
            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            # case will never enter
            # if not token.session_key and "token" not in self.request.GET:
            #     return self.replace_token()
            if token.extra.get("prot_strength", 0) >= 4:
                self.request.is_special_user = True
                self.request.is_owner = True
            self.request.auth_token = token
            return True

        # if result is impossible and token invalid try to login
        if minstrength >= 4 and not self.usercomponent.can_auth:
            # remove token and redirect
            # login_url can be also on a different host => merge_get_url
            target = "{}?{}={}".format(
                self.get_login_url(),
                REDIRECT_FIELD_NAME,
                quote_plus(
                    merge_get_url(
                        self.request.get_full_path(),
                        token=None
                    )
                )
            )
            return HttpResponseRedirect(redirect_to=target)

        protection_codes = None
        if "protection" in self.request.GET:
            protection_codes = self.request.GET.getlist("protection")
        # execute protections for side effects even no_token
        self.request.protections = self.usercomponent.auth(
            request=self.request, scope=self.scope,
            protection_codes=protection_codes, ptype=ptype
        )
        if (
            type(self.request.protections) is int and  # because: False==0
            self.request.protections >= minstrength
        ):
            # generate no token if not required
            if no_token:
                return True

            token = self.create_token(
                extra={
                    "strength": self.usercomponent.strength,
                    "prot_strength": self.request.protections
                }
            )

            if token.extra["prot_strength"] >= 4:
                self.request.is_special_user = True
                self.request.is_owner = True

            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            self.request.auth_token = token
            if "token" in self.request.GET:
                return self.replace_token()
            return True
        return False

    def has_special_access(
        self, user_by_login=True, user_by_token=False,
        staff=False, superuser=False
    ) -> bool:
        if self.request.user.is_authenticated:
            t = self.get_travel_for_request().exists()
            # auto activate but not deactivate
            if t:
                self.request.session["is_travel_protected"] = t
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if user_by_login and self.request.user == self.usercomponent.user:
            self.request.is_owner = True
            self.request.is_special_user = True
            return True
        if user_by_token and self.test_token(4) is True:
            return True

        # remove user special state if is_travel_protected
        if self.request.session.get("is_travel_protected", False):
            return False
        if superuser and self.request.user.is_superuser:
            self.request.is_special_user = True
            self.request.is_staff = True
            return True
        if staff and self.request.user.is_staff:
            if type(staff) is bool:
                self.request.is_special_user = True
                self.request.is_staff = True
                return True
            if not isinstance(staff, (tuple, list, set)):
                staff = (staff,)

            if not all(
                map(self.request.user.has_perm, staff)
            ):
                return False
            self.request.is_special_user = True
            self.request.is_staff = True
            return True
        return False

    def get_user(self):
        """ Get user from user field or request """
        if (
                "user" not in self.kwargs and
                self.request.user.is_authenticated
           ):
            return self.request.user

        model = get_user_model()
        margs = {model.USERNAME_FIELD: None}
        margs[model.USERNAME_FIELD] = self.kwargs.get("user", None)
        return get_object_or_404(
            model.objects.select_related("spider_info"),
            **margs
        )

    def get_usercomponent(self):
        query = {
            "token": self.kwargs["token"]
        }
        return get_object_or_404(
            UserComponent.objects.prefetch_related(
                "authtokens", "protections"
            ),
            **query
        )

    def handle_no_permission(self):
        # in case no protections are used (e.g. add content)
        p = getattr(self.request, "protections", False)
        if not bool(p):
            # return 403
            return super().handle_no_permission()
        # should be never true here
        assert(p is not True)
        context = {
            "spider_GET": self.sanitize_GET(),
            "LOGIN_URL": self.get_login_url(),
            "scope": getattr(self, "scope", None),
            "uc": self.usercomponent,
            "object": getattr(self, "object", None),
            "is_public_view": self.usercomponent.public
        }
        return self.response_class(
            request=self.request,
            template=self.get_noperm_template_names(),
            # render with own context; get_context_data may breaks stuff or
            # disclose informations
            context=context,
            using=self.template_engine,
            content_type=self.content_type
        )

    def get_noperm_template_names(self):
        return "spider_base/protections/protections.html"


class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # for protections & contents
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        # for protections & contents
        return self.get(request, *args, **kwargs)


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

    def test_token(self, minstrength, force_token=False):
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
                # maximal one main intention
                if len(intentions.difference(VALID_SUB_INTENTIONS)) > 1:
                    return HttpResponse(
                        "invalid intentions", status=400
                    )
                minstrength = 4
        return super().test_token(minstrength, force_token)

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
        try:
            d = {
                "token": token.token,
                "hash_algorithm": settings.SPIDER_HASH_ALGORITHM.name,
                "renew": "false"
            }
            if context["payload"]:
                d["payload"] = context["payload"]

            ret = requests.post(
                context["referrer"],
                data=d,
                headers={
                    "Referer": merge_get_url(
                        "%s%s" % (
                            context["hostpart"],
                            self.request.path
                        )
                        # sending full url not required anymore, payload
                        # token=None, referrer=None, raw=None, intention=None,
                        # sl=None, payload=None
                    )
                },
                **get_requests_params(context["referrer"])
            )
            ret.raise_for_status()
        except requests.exceptions.SSLError as exc:
            logging.info(
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
        except Exception as exc:
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
            logging.info(
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
        h.update(token.token.encode("ascii", "ignore"))
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
        if "persist" in context["intentions"]:
            # cannot add sl intention
            if "intentions" in token.extra:
                if "sl" in context["intentions"].difference(
                    token.extra["intentions"]
                ):
                    return False
            # set persist = true, (false=-1)
            token.persist = 0
            # if possible, pin to anchor
            if self.usercomponent.primary_anchor:
                token.persist = self.usercomponent.primary_anchor.id
        else:
            # check if token was reused if not persisted
            if token.referrer:
                return False

        if "initial_referrer_url" not in token.extra:
            token.extra["initial_referrer_url"] = "{}://{}{}".format(
                self.request.scheme,
                self.request.get_host(),
                self.request.path
            )
        return True

    def handle_referrer(self):
        _ = gettext
        if (
            self.request.user != self.usercomponent.user and
            not self.request.auth_token
        ):
            return HttpResponseRedirect(
                redirect_to="{}?{}={}".format(
                    self.get_login_url(),
                    REDIRECT_FIELD_NAME,
                    quote_plus(
                        merge_get_url(
                            self.request.get_full_path(),
                            token=None
                        )
                    )
                )
            )

        context = self.get_context_data()
        context["intentions"] = set(self.request.GET.getlist("intention"))
        context["payload"] = self.request.GET.get("payload", None)
        context["is_serverless"] = "sl" in context["intentions"]
        context["referrer"] = merge_get_url(self.request.GET["referrer"])
        context["old_search"] = []
        context["object_list"] = self.object_list
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
        delete_auth_token = False

        action = self.request.POST.get("action", None)
        if "domain" in context["intentions"]:
            # domain mode only possible for token without user
            token = self.request.auth_token
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
            token.create_auth_token()
            token.referrer = ReferrerObject.objects.get_or_create(
                url=context["referrer"]
            )[0]
            token.extra["intentions"] = list(context["intentions"])
            try:
                token.save()
            except TokenCreationError:
                logging.exception("Token creation failed")
                return HttpResponseServerError(
                    "Token creation failed, try again"
                )
            context["post_success"] = False
            ret = self.refer_with_post(context, token)
            if not context["post_success"]:
                token.delete()
            return ret
        elif action == "confirm":
            token = None
            hasoldtoken = False
            # if persist try to find old token
            if "persist" in context["intentions"]:
                persistfind = Q(persist=0, usercomponent=self.usercomponent)
                persistfind |= Q(
                    persist__in=self.usercomponent.contents.filter(
                        info__contains="\x1eanchor\x1e"
                    ).values_list("id", flat=True)
                )
                token = AuthToken.objects.filter(
                    persistfind,
                    referrer__url=context["referrer"]
                ).first()
                if token:
                    hasoldtoken = True
                    # migrate usercomponent
                    token.usercomponent = self.usercomponent

            # create only new token when admin token and not persisted token
            if self.usercomponent.user == self.request.user:
                # boost strength if user is owner
                # token is not auth_token
                if token:
                    token.extra["strength"] = 10
                    # self.request new token
                    token.create_auth_token()
                else:
                    token = AuthToken(
                        usercomponent=self.usercomponent,
                        extra={
                            "strength": 10
                        }
                    )
            else:
                # either reuse persistent token with auth token tokenstring
                # or just reuse auth token
                if token:
                    # slate auth token for destruction
                    delete_auth_token = True
                    # steal token value
                    token.token = self.request.auth_token.token
                else:
                    # repurpose token
                    # NOTE: one token, one referrer
                    token = self.request.auth_token

            # set to zero as prot_strength can elevate perms
            token.extra["prot_strength"] = 0
            token.extra["intentions"] = list(context["intentions"])

            if not self.clean_refer_intentions(context, token):
                return HttpResponseRedirect(
                    redirect_to=merge_get_url(
                        context["referrer"],
                        error="intentions_incorrect"
                    )
                )

            token.extra["filter"] = self.request.POST.getlist("search")
            if "live" in context["intentions"]:
                token.extra.pop("ids", None)
            else:
                token.extra["ids"] = list(
                    self.object_list.values_list("id", flat=True)
                )
            token.referrer = ReferrerObject.objects.get_or_create(
                url=context["referrer"]
            )[0]
            # after cleanup, save
            try:
                with transaction.atomic():
                    # must be done here, elsewise other token can (unlikely)
                    # take token as it is free for a short time, better be safe
                    if delete_auth_token:
                        # delete old token
                        self.request.auth_token.delete()
                    token.save()
            except TokenCreationError:
                logging.exception("Token creation failed")
                return HttpResponseServerError(
                    _("Token creation failed, try again")
                )

            if context["is_serverless"]:
                context["post_success"] = True
                ret = self.refer_with_get(context, token)
            else:
                context["post_success"] = False
                ret = self.refer_with_post(context, token)
            if not context["post_success"] and not hasoldtoken:
                token.delete()
            return ret

        elif action == "cancel":
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    status="canceled",
                    payload=context["payload"]
                )
            )
        else:
            token = None
            oldtoken = None
            # use later reused token early
            if self.usercomponent.user != self.request.user:
                token = self.request.auth_token
            # don't re-add search parameters, only initialize
            if (
                self.request.method != "POST" and
                "persist" in context["intentions"]
            ):
                persistfind = Q(persist=0, usercomponent=self.usercomponent)
                persistfind |= Q(
                    persist__in=self.usercomponent.contents.filter(
                        info__contains="\x1eanchor\x1e"
                    ).values_list("id", flat=True)
                )
                oldtoken = AuthToken.objects.filter(
                    persistfind,
                    referrer__url=context["referrer"],
                ).first()

            if oldtoken:
                context["old_search"] = oldtoken.extra.get("search", [])
            if not self.clean_refer_intentions(context, token):
                return HttpResponse(
                    status=400,
                    content=_('Error: intentions incorrect')
                )
            return self.response_class(
                request=self.request,
                template=self.get_referrer_template_names(),
                context=context,
                using=self.template_engine,
                content_type=self.content_type
            )

    def get_referrer_template_names(self):
        return "spider_base/protections/referring.html"


class EntityDeletionMixin(UserTestMixin):
    object = None
    http_method_names = ['get', 'post', 'delete']

    def get_context_data(self, **kwargs):
        _time = self.get_required_timedelta()
        if _time and self.object.deletion_requested:
            now = timezone.now()
            if self.object.deletion_requested + _time >= now:
                kwargs["remaining"] = timedelta(seconds=0)
            else:
                kwargs["remaining"] = self.object.deletion_requested+_time-now
        return super().get_context_data(**kwargs)

    def get_required_timedelta(self):
        _time = self.object.deletion_period
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = self.request.get_host()
        ret["Access-Control-Allow-Methods"] = "POST, GET, DELETE, OPTIONS"
        return ret

    def delete(self, request, *args, **kwargs):
        _time = self.get_required_timedelta()
        if _time:
            now = timezone.now()
            if self.object.deletion_requested:
                if self.object.deletion_requested+_time >= now:
                    return self.get(request, *args, **kwargs)
            else:
                self.object.deletion_requested = now
                self.object.save()
                return self.get(request, *args, **kwargs)
        self.object.delete()
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        # delete works if allowed in CORS
        if request.POST.get("action") == "reset":
            return self.reset(request, *args, **kwargs)
        elif request.POST.get("action") == "delete":
            return self.delete(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def reset(self, request, *args, **kwargs):
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())
