__all__ = (
    "UserTestMixin", "UCTestMixin", "EntityDeletionMixin", "ReferrerMixin"
)

import logging
import hashlib
from urllib.parse import quote_plus

from datetime import timedelta


from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.http import (
    HttpResponseRedirect, HttpResponseServerError, HttpResponse
)
from django.utils import timezone
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext


import requests
import certifi

from ..helpers import merge_get_url, get_settings_func
from ..constants import (
    VariantType, index_names, VALID_INTENTIONS
)
from ..models import (
    UserComponent, AuthToken, TokenCreationError
)


class UserTestMixin(AccessMixin):
    no_nonce_usercomponent = False
    also_authenticated_users = False
    preserved_GET_parameters = set(["token", "protection"])
    login_url = reverse_lazy(getattr(
        settings,
        "LOGIN_URL",
        "auth:login"
    ))

    def dispatch_extra(self, request, *args, **kwargs):
        return None

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
        self.request.is_elevated_request = False
        self.request.is_owner = False
        self.request.is_special_user = False
        self.request.auth_token = None
        try:
            user_test_result = self.test_func()
        except TokenCreationError as e:
            logging.exception(e)
            return HttpResponseServerError(
                _("Token creation failed, try again")
            )
        if not user_test_result:
            return self.handle_no_permission()
        if isinstance(user_test_result, str):
            return HttpResponseRedirect(redirect_to=user_test_result)
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

    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = VariantType.raw_update.value
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        kwargs["spider_GET"] = self.sanitize_GET()
        return super().get_context_data(**kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

    def replace_token(self):
        GET = self.request.GET.copy()
        GET["token"] = self.request.auth_token.token
        return "?".join((self.request.path, GET.urlencode()))

    def create_token(self, special_user=None, extra=None):
        d = {
            "usercomponent": self.usercomponent,
            "session_key": None,
            "created_by_special_user": special_user,
            "extra": {}
        }
        if "token" not in self.request.GET:
            d["session_key"] = self.request.session.session_key

        token = None
        if "persist" in self.request.GET.getlist("intention"):
            if self.request.GET.get("referrer", None) is None:
                return False
            referrer = merge_get_url(self.request.GET["referrer"])
            token = AuthToken.objects.filter(
                usercomponent=self.usercomponent, referrer=referrer,
                persist=True
            ).first()
            if token:
                token.create_auth_token()
        if not token:
            token = AuthToken(**d)
        if extra:
            token.extra.update(extra)
        token.save()
        return token

    def create_admin_token(self):
        expire = timezone.now()-self.usercomponent.token_duration
        # delete old token, so no confusion happen
        self.usercomponent.authtokens.filter(
            created__lt=expire
        ).delete()
        # delete tokens from old sessions
        self.usercomponent.authtokens.exclude(
            session_key=self.request.session.session_key,
        ).filter(created_by_special_user=self.request.user).delete()

        # use session_key, causes deletion on logout
        token = self.usercomponent.authtokens.filter(
            session_key=self.request.session.session_key
        ).first()
        if token:
            return token
        return self.create_token(
            self.request.user,
            extra={
                "weak": False,
                "strength": 10
            }
        )

    def remove_old_tokens(self, expire=None):
        if not expire:
            expire = timezone.now()-self.usercomponent.token_duration
        return self.usercomponent.authtokens.filter(
            created__lt=expire, persist=False
        ).delete()

    def test_token(self):
        expire = timezone.now()-self.usercomponent.token_duration
        tokenstring = self.request.GET.get("token", None)
        no_token = (self.usercomponent.required_passes == 0)

        # token not required
        if not no_token or tokenstring:
            # delete old token, so no confusion happen
            self.remove_old_tokens(expire)

            # generate key if not existent
            if not self.request.session.session_key:
                self.request.session.cycle_key()

            # only valid tokens here
            tokenstring = self.request.GET.get("token", None)
            if tokenstring or not self.request.session.session_key:
                # find by tokenstring
                token = self.usercomponent.authtokens.filter(
                    token=tokenstring
                ).first()
            else:
                # use session_key
                token = self.usercomponent.authtokens.filter(
                    session_key=self.request.session.session_key
                ).first()
            if token:
                self.request.token_expires = \
                    token.created+self.usercomponent.token_duration
                self.request.auth_token = token
                # case will never enter
                # if not token.session_key and "token" not in self.request.GET:
                #     return self.replace_token()
                if (
                    self.usercomponent.strength >=
                    settings.MIN_STRENGTH_EVELATION
                ):
                    self.request.is_elevated_request = True
                return True

        protection_codes = None
        if "protection" in self.request.GET:
            protection_codes = self.request.GET.getlist("protection")
        # execute protections for side effects even no_token
        self.request.protections = self.usercomponent.auth(
            request=self.request, scope=self.scope,
            protection_codes=protection_codes
        )
        if self.request.protections is True:
            # token not required
            if no_token:
                return True
            # is_elevated_request requires token
            if (
                self.usercomponent.strength >=
                settings.MIN_STRENGTH_EVELATION
            ):
                self.request.is_elevated_request = True

            token = self.create_token(
                strength=self.usercomponent.strength
            )

            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            self.request.auth_token = token
            if "token" in self.request.GET:
                return self.replace_token()
            return True
        return False

    def has_special_access(
        self, user=True, staff=False, superuser=True, staff_perm=None
    ):
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if self.request.user == self.usercomponent.user:
            self.request.is_elevated_request = True
            self.request.is_owner = True
            self.request.is_special_user = True
            return True
        # remove user special state if is_fake
        if self.request.session.get("is_fake", False):
            return False
        if superuser and self.request.user.is_superuser:
            self.request.is_elevated_request = True
            self.request.is_special_user = True
            return True
        if staff and self.request.user.is_staff:
            if not staff_perm or self.request.user.has_perm(staff_perm):
                self.request.is_elevated_request = True
                self.request.is_special_user = True
                return True
        return False

    def get_user(self):
        """ Get user from user field or request """
        if (
                self.also_authenticated_users and
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
        ucname = self.kwargs["name"]
        if ucname in index_names:
            if self.request.session["is_fake"]:
                ucname = "fake_index"
            else:
                ucname = "index"
        query = {
            "name": ucname,
            "user": self.get_user()
        }
        if not self.no_nonce_usercomponent:
            query["nonce"] = self.kwargs["nonce"]
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
            return super().handle_no_permission()
        # should be never true here
        assert(p is not True)
        context = {
            "spider_GET": self.sanitize_GET(),
            "LOGIN_URL": self.get_login_url(),
            "scope": getattr(self, "scope", None),
            "uc": self.usercomponent,
            "index_names": index_names,
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
        return "spider_protections/protections.html"


class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)


class ReferrerMixin(object):
    def get_context_data(self, **kwargs):
        kwargs["token_strength"] = None
        # will be overwritten in referring path so there is no interference
        kwargs["referrer"] = None
        kwargs["intentions"] = []
        if self.request.auth_token:
            kwargs["referrer"] = self.request.auth_token.extra.get(
                "referrer", None
            )
            kwargs["token_strength"] = self.request.auth_token.extra.get(
                "strength", None
            )
            kwargs["intentions"] = set(self.request.auth_token.extra.get(
                "intentions", []
            ))
        return super().get_context_data(**kwargs)

    def refer_with_post(self, context, token):
        # application/x-www-form-urlencoded is best here,
        # for beeing compatible to most webservers
        # client side rdf is no problem
        # NOTE: csrf must be disabled or use csrf token from GET,
        #       here is no way to know the token value
        try:
            d = {
                "token": token.token,
                "hash_algorithm": settings.SPIDER_HASH_ALGORITHM
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
                        # not required anymore, payload
                        # token=None, referrer=None, raw=None, intention=None,
                        # sl=None, payload=None
                    )
                },
                verify=certifi.where()
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
            logging.info(
                "post failed: \"%s\" failed",
                context["referrer"], exc_info=exc
            )
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    status="post_failed",
                    error=""
                )
            )
        context["post_success"] = True
        h = hashlib.new(settings.SPIDER_HASH_ALGORITHM)
        h.update(token.token.encode("ascii", "ignore"))
        return HttpResponseRedirect(
            redirect_to=merge_get_url(
                context["referrer"],
                status="success",
                hash=h.hexdigest()
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

    def check_refer_intentions(self, context, token=None):
        # First error: may not be used with sl:
        #  this way rogue client based attacks are prevented
        if context["is_serverless"]:
            return False

        # Second error: invalid intentions or combinations
        if not context["intentions"].issubset(VALID_INTENTIONS):
            return False
        if not token:
            return True
        # check if token was reused
        if token.referrer is not None:
            return False
        if token.extra.get("intentions", None) is not None:
            return False
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
                    quote_plus(self.request.get_full_path())
                )
            )

        context = self.get_context_data()
        context["intentions"] = set(self.request.GET.getlist("intention"))
        context["payload"] = self.request.GET.get("intention", None)
        context["is_serverless"] = (
            self.request.GET.get("sl", "") == "true"
        )
        context["referrer"] = merge_get_url(self.request.GET["referrer"])
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(context["referrer"]):
            return HttpResponse(
                status=400,
                content=_('Insecure url: %(url)s') % {
                    "url": context["referrer"]
                }
            )
        context["object_list"] = self.object_list

        action = self.request.POST.get("action", None)
        if action == "confirm":
            # create only new token when admin token
            if self.usercomponent.user == self.request.user:
                token = AuthToken(
                    usercomponent=self.usercomponent,
                    extra={
                        "ids": list(
                            self.object_list.values_list("id", flat=True)
                        ),
                        "weak": False,
                        "strength": 10
                    }
                )
            else:
                # repurpose token
                # NOTE: one token, one referrer
                token = self.request.auth_token
            if context["intentions"]:
                if not self.check_refer_intentions(context, token):
                    return HttpResponseRedirect(
                        redirect_to=merge_get_url(
                            context["referrer"],
                            error="intentions_incorrect"
                        )
                    )
                token.extra["intentions"] = list(context["intentions"])
            else:
                token.extra["intentions"] = []
            token.referrer = context["referrer"]
            # after cleanup, save deletion token
            try:
                token.save()
            except TokenCreationError as e:
                logging.exception(e)
                return HttpResponseServerError(
                    _("Token creation failed, try again")
                )

            if context["is_serverless"]:
                return self.refer_with_get(context, token)
            context["post_success"] = False
            ret = self.refer_with_post(context, token)
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
            if context["intentions"]:
                token = None
                if self.usercomponent.user != self.request.user:
                    token = self.request.auth_token
                if not self.check_refer_intentions(context, token):
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
        return "spider_protections/referring.html"


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
        _time = self.object.content.deletion_period
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def delete(self, request, *args, **kwargs):
        # hack for compatibility to ContentRemove
        if getattr(self.object, "name", "") in index_names:
            return self.handle_no_permission()
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
        # because forms are screwed (delete not possible)
        if request.POST.get("action") == "reset":
            return self.reset(request, *args, **kwargs)
        elif request.POST.get("action") == "delete":
            return self.delete(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def reset(self, request, *args, **kwargs):
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())
