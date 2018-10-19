__all__ = ("UserTestMixin", "UCTestMixin")

import logging
import hashlib
from urllib.parse import urlencode

import requests
import certifi

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.utils import timezone
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext
from django.http import JsonResponse

from ..helpers import join_get_url
from ..constants import UserContentType, index_names
from ..models import (
    UserComponent, AuthToken, TokenCreationError
)


class UserTestMixin(AccessMixin):
    no_nonce_usercomponent = False
    also_authenticated_users = False
    allowed_GET_parameters = set(["token", "raw", "protection"])
    login_url = getattr(
        settings,
        "LOGIN_URL",
        reverse_lazy("auth:login")
    )

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
        self.request.is_elevated_request = False
        self.request.is_owner = False
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
        if "referrer" in self.request.GET:
            # don't want to have to clean up, GET is easier
            assert("token" in self.request.GET)
            return self.handle_referrer()
        return super().dispatch(request, *args, **kwargs)

    def sanitize_GET(self):
        GET = self.request.GET.copy()
        for key in list(GET.keys()):
            if key not in self.allowed_GET_parameters:
                GET.pop(key, None)
        return GET

    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = UserContentType.raw_update.value
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

    def test_token(self):
        expire = timezone.now()-self.usercomponent.token_duration
        no_token = self.usercomponent.required_passes == 0

        # token not required
        if not no_token:
            # delete old token, so no confusion happen
            self.usercomponent.authtokens.filter(
                created__lt=expire
            ).delete()

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
                if "token" not in self.request.GET:
                    return self.replace_token()
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
            session_key = None
            if "token" not in self.request.GET:
                session_key = self.request.session.session_key
            token = AuthToken(
                usercomponent=self.usercomponent,
                session_key=session_key
            )
            token.save()

            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            self.request.auth_token = token
            if "token" in self.request.GET:
                return self.replace_token()
            if (
                self.usercomponent.strength >=
                settings.MIN_STRENGTH_EVELATION
            ):
                self.request.is_elevated_request = True
            return True
        return False

    def has_special_access(self, user=True, staff=False, superuser=True):
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if self.request.user == self.usercomponent.user:
            self.request.is_elevated_request = True
            self.request.is_owner = True
            return True
        # remove user special state if is_fake
        if self.request.session.get("is_fake", False):
            return False
        if superuser and self.request.user.is_superuser:
            self.request.is_elevated_request = True
            return True
        if staff and self.request.user.is_staff:
            self.request.is_elevated_request = True
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
        if "raw" in self.request.GET:
            if context["scope"] == "view":
                context["scope"] = "raw"
            return JsonResponse(
                {
                    "scope": context["scope"],
                    "protections": [
                        prot.protection.render_raw(prot.result)
                        for prot in self.request.protections
                    ]
                }
            )
        return self.response_class(
            request=self.request,
            template=self.get_noperm_template_names("raw" in self.request.GET),
            # render with own context; get_context_data may breaks stuff or
            # disclose informations
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
            return HttpResponseRedirect(
                redirect_to="{}?{}={}".format(
                    self.get_login_url(),
                    REDIRECT_FIELD_NAME,
                    urlencode(self.request.GET["referrer"])
                )
            )
        context = self.get_context_data()
        context["referrer"] = "https://{}".format(
            self.request.GET["referrer"]
        )
        if "confirm" in self.request.POST:
            if self.usercomponent.user == self.request.user:
                authtoken = AuthToken(
                    usercomponent=self.usercomponent
                )
                try:
                    authtoken.save()
                except TokenCreationError as e:
                    logging.exception(e)
                    return HttpResponseServerError(
                        _("Token creation failed, try again")
                    )
                token = authtoken.token
            else:
                token = self.request.auth_token.token
            # www-data is best here, for beeing compatible to webservers
            # webservers can transfer dictionary to logic (this program) where
            # json is no problem
            ret = requests.post(
                context["referrer"],
                data={
                    "token": token,
                    "hash_algorithm": settings.SPIDER_HASH_ALGORITHM,
                    "url": "%s%s" % (
                        context["hostpart"],
                        self.request.get_full_path()
                    )
                },
                verify=certifi.where()
            )
            if ret.status_code not in (200, 201):
                return HttpResponseRedirect(
                    redirect_to=join_get_url(
                        context["referrer"],
                        error="post_failed"
                    )
                )
            h = hashlib.new(settings.SPIDER_HASH_ALGORITHM)
            h.update(token.encode("ascii", "ignore"))
            return HttpResponseRedirect(
                redirect_to=join_get_url(
                    context["referrer"],
                    hash=h.hexdigest()
                )
            )
        else:
            if "raw" in self.request.GET:
                ret = {
                    "scope": context["scope"],
                }
                if isinstance(self.object, UserComponent):
                    ret["contents"] = [str(ob) for ob in self.object.contents]
                else:
                    ret["contents"] = [str(self.object)]
                ret["name"] = str(self.object)
                return JsonResponse(ret)
            return self.response_class(
                request=self.request,
                template=self.get_referrer_template_names(),
                context=context,
                using=self.template_engine,
                content_type=self.content_type
            )

    def get_referrer_template_names(self):
        return "spider_protections/referring.html"

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
