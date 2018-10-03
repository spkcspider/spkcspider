__all__ = ("UserTestMixin", "UCTestMixin")

import logging

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.conf import settings

from ..constants import UserContentType
from ..models import (
    UserComponent, AuthToken, TokenCreationError
)


class UserTestMixin(AccessMixin):
    no_nonce_usercomponent = False
    also_authenticated_users = False

    def dispatch(self, request, *args, **kwargs):
        self.request.is_elevated_request = False
        self.request.is_owner = False
        self.request.auth_token = None
        user_test_result = self.test_func()
        if not user_test_result:
            return self.handle_no_permission()
        if isinstance(user_test_result, str):
            return HttpResponseRedirect(redirect_to=user_test_result)
        return super().dispatch(request, *args, **kwargs)

    def sanitize_GET(self):
        GET = self.request.GET.copy()
        for key in list(GET.keys()):
            if key not in [
                "prefer_get", "token", "deref", "raw", "protection"
            ]:
                GET.pop(key, None)
        return GET

    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = UserContentType.raw_update.value
        if "nonpublic" not in kwargs:
            kwargs["nonpublic"] = True
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

    def replace_prefer_get(self):
        GET = self.request.GET.copy()
        # should not fail as only executed when positive
        token = self.request.auth_token.token
        if (
            GET.get("token", "") != token and
            (
                self.request.GET.get("prefer_get", "") == "true" or
                not self.request.session.session_key
            )
        ):
            GET["token"] = token
            # not required anymore, token does the same + authorizes
            GET.pop("prefer_get", None)
            return "?".join((self.request.path, GET.urlencode()))
        return True

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
                return self.replace_prefer_get()

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
            token = AuthToken(
                usercomponent=self.usercomponent,
                session_key=self.request.session.session_key
            )
            try:
                token.save()
            except TokenCreationError as e:
                logging.exception(e)
                return False
            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            self.request.auth_token = token
            return self.replace_prefer_get()
        return False

    def has_special_access(self, user=True, staff=False, superuser=True):
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if self.usercomponent.strength >= settings.MIN_STRENGTH_EVELATION:
            self.request.is_elevated_request = True
        if self.request.user == self.usercomponent.user:
            self.request.is_elevated_request = True
            self.request.is_owner = True
            return True
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
        return get_object_or_404(model, **margs)

    def get_usercomponent(self):
        ucname = self.kwargs["name"]
        if ucname in ("index", "fake_index"):
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
        return get_object_or_404(UserComponent, **query)

    def handle_no_permission(self):
        # in case no protections are used (e.g. add content)
        p = getattr(self.request, "protections", False)
        if not bool(p):
            return super().handle_no_permission()
        # should be never true here
        assert(p is not True)
        return self.response_class(
            request=self.request,
            template=self.get_noperm_template_names(),
            # render with own context; get_context_data may breaks stuff or
            # disclose informations
            context={},
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
