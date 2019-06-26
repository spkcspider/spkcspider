__all__ = (
    "UserTestMixin", "UCTestMixin", "EntityDeletionMixin", "DefinitionsMixin"
)
import logging
from urllib.parse import quote_plus

from datetime import timedelta

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.http.response import HttpResponseBase
from django.utils import timezone
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext

from ..helpers import merge_get_url
from ..constants import (
    VariantType, TokenCreationError, ProtectionType,
    loggedin_active_tprotections
)
from ..models import UserComponent, AuthToken, TravelProtection

logger = logging.getLogger(__name__)


class DefinitionsMixin(object):
    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = VariantType.raw_update.value
        kwargs["component_feature_type"] = VariantType.component_feature.value
        kwargs["content_feature_type"] = VariantType.content_feature.value
        kwargs["no_export_type"] = VariantType.no_export.value
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        return super().get_context_data(**kwargs)


class UserTestMixin(DefinitionsMixin, AccessMixin):
    preserved_GET_parameters = set(["token", "protection"])
    login_url = reverse_lazy(getattr(
        settings,
        "LOGIN_URL",
        "auth:login"
    ))
    # don't allow AccessMixin to redirect, handle in test_token
    raise_exception = True
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
            logger.exception("Token creation failed")
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
        kwargs["sanitized_GET"] = self.sanitize_GET()
        if kwargs["sanitized_GET"]:
            kwargs["sanitized_GET"] = "{}&".format(
                kwargs["sanitized_GET"].urlencode()
            )
        else:
            kwargs["sanitized_GET"] = ""
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

    def test_token(self, minstrength=0, force_token=False, taint=False):
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
            if (
                token.extra["prot_strength"] >= 4 and
                not token.extra.get("taint", False)
            ):
                self.request.is_special_user = True
                self.request.is_owner = True
            self.request.auth_token = token
            return True

        # if result is impossible and token invalid try to login
        if minstrength >= 4 and not self.usercomponent.can_auth:
            # auth won't work for logged in users
            if self.request.user.is_authenticated:
                return False
            # remove token and redirect
            # login_url can be also on a different host => merge_get_url
            target = "{}?{}={}".format(
                self.get_login_url(),
                REDIRECT_FIELD_NAME,
                quote_plus(
                    merge_get_url(
                        self.request.build_absolute_uri(),
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
            # generate only tokens if required
            if no_token:
                return True

            token = self.create_token(
                extra={
                    "strength": self.usercomponent.strength,
                    "prot_strength": self.request.protections,
                    "taint": taint
                }
            )

            if (
                token.extra["prot_strength"] >= 4 and
                not token.extra.get("taint", False)
            ):
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
            t = self.get_travel_for_request().filter(
                login_protection__in=loggedin_active_tprotections
            ).exists()
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
            "sanitized_GET": self.sanitize_GET(),
            "LOGIN_URL": self.get_login_url(),
            "scope": getattr(self, "scope", None),
            "uc": self.usercomponent,
            "object": getattr(self, "object", None),
            "is_public_view": self.usercomponent.public
        }
        assert len(p) > 0
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
