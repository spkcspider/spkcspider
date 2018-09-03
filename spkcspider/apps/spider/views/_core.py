__all__ = ("UserTestMixin", "UCTestMixin")

import logging

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.utils import timezone

from ..constants import ProtectionType, UserContentType
from ..models import UserComponent, AuthToken, TokenCreationError


class UserTestMixin(AccessMixin):
    no_nonce_usercomponent = False
    also_authenticated_users = False

    def dispatch(self, request, *args, **kwargs):
        self.request.is_priv_requester = False
        self.request.is_owner = False
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
        kwargs["UserContentType"] = UserContentType
        kwargs["ProtectionType"] = ProtectionType
        kwargs["spider_GET"] = self.sanitize_GET()
        return super().get_context_data(**kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

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

            # only valid tokens here yeah
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
                # self.request.is_priv_requester = True
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
            # self.request.is_priv_requester = True
            token = AuthToken(
                usercomponent=self.usercomponent,
                session_key=self.request.session.session_key
            )
            try:
                token.save()
            except TokenCreationError as e:
                logging.exception(e)
                return True
            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            GET = self.request.GET.copy()
            if (
                    self.request.GET.get("prefer_get", "") == "true" or
                    "token" in self.request.GET or
                    not self.request.session.session_key
               ):
                GET["token"] = token.token
                # not required anymore, token does the same + authorizes
                GET.pop("prefer_get", None)
            return "?".join((self.request.path, GET.urlencode()))
        return False

    def has_special_access(self, user=True, staff=False, superuser=True):
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if not self.usercomponent.public:
            self.request.is_priv_requester = True
        if self.request.user == self.usercomponent.user:
            self.request.is_priv_requester = True
            self.request.is_owner = True
            return True
        if superuser and self.request.user.is_superuser:
            self.request.is_priv_requester = True
            return True
        if staff and self.request.user.is_staff:
            self.request.is_priv_requester = True
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
        query = {"name": self.kwargs["name"]}
        query["user"] = self.get_user()
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
