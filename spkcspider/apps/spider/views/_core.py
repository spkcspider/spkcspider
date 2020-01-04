__all__ = (
    "UserTestMixin", "UCTestMixin", "DefinitionsMixin"
)
import logging
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.mixins import AccessMixin
from django.db import models
from django.forms.widgets import Media
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext

from spkcspider.constants import (
    ProtectionType, TokenCreationError, VariantType,
)

from spkcspider.utils.urls import merge_get_url

from ..models import AssignedContent, AuthToken, UserComponent
from ..queryfilters import loggedin_active_tprotections_q

logger = logging.getLogger(__name__)


class DefinitionsMixin(object):
    user_model = None

    def get_context_data(self, **kwargs):
        kwargs["VariantType"] = VariantType
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        kwargs.setdefault("media", Media())
        return super().get_context_data(**kwargs)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.user_model = get_user_model()


class ExpiryMixin(DefinitionsMixin):
    protected_objects = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.protected_objects = set()

    def calculate_deletion_content(self, content, del_requested):
        if content.deletion_requested:
            return {
                "ob": content,
                "deletion_date":
                    content.deletion_requested+content.deletion_period,
                "deletion_active": True
            }
        else:
            return {
                "ob": content,
                "deletion_date": del_requested+content.deletion_period,
                "deletion_active": False
            }

    def calculate_deletion_component(
        self, uc, now, ignoredids=frozenset(), log=None,
        del_expired=False
    ):
        """
        Calculate earliest deletion date

        Arguments:
            uc {Usercomponent} -- Usercomponent which should be analysed
            now {datetime} -- Current date

        Keyword Arguments:
            ignoredids {set} -- ignore for mimimum date calculation (default: {frozenset()})
            log {dict} -- data spy for contents (default: {None})
            del_expired {bool,"only"} -- False: don't change anything True: delete expired and calculate minimal deletion date, "only": delete only expired (default: {False})

        Returns:
            None -- deletion of component successful
            False -- No deletion active (only with del_expired="only")
            datetime -- Earliest deletion date
        """  # noqa E501
        del_requested = uc.deletion_requested or now

        def _helper(content):
            ret = self.calculate_deletion_content(content, del_requested)
            if ret["deletion_active"]:
                if (
                    del_expired and
                    ret["deletion_date"] <= now
                ):
                    try:
                        content.delete()
                        return None
                    except models.ProtectedError:
                        self.protected_objects.add(content)
            if content.id in ignoredids:
                return None
            if log is not None:
                log[content.id] = ret
            return ret["deletion_date"]

        ret_list = []
        q = models.Q()
        if del_expired == "only":
            q = models.Q(deletion_requested__isnull=False)
        if del_expired != "only" or uc.deletion_requested:
            q |= ~models.Q(id__in=ignoredids)
            ret_list.append(del_requested + uc.deletion_period)
        query = uc.contents.filter(q)
        if log is None:
            query = query.only(
                "id", "deletion_requested"
            )
        ret_list.extend(filter(
            None,
            map(_helper, query)
        ))
        if not ret_list:
            return False
        ret = max(ret_list)

        if (
            del_expired and
            uc.deletion_requested and
            ret <= now and
            not uc.is_index
        ):
            uc.delete()
            return None
        return ret

    def remove_old_entities(self, ob=None, now=None):
        if not now:
            now = timezone.now()
        if isinstance(ob, AssignedContent):
            result = self.calculate_deletion_content(ob, now)
            if (
                result["deletion_active"] and
                result["deletion_date"] <= now
            ):
                try:
                    ob.delete()
                except models.ProtectedError:
                    self.protected_objects.add(ob)
                    return False
                return True
        elif isinstance(ob, UserComponent):
            deletion_date = \
                self.calculate_deletion_component(
                    ob, now, del_expired="only"
                )
            # deletion_date is None: deleted
            if deletion_date is None:
                return True
        elif isinstance(ob, int):
            for uc in UserComponent.objects.filter(
                models.Q(deletion_requested__isnull=False) |
                models.Q(contents__deletion_requested__isnull=False)
            ).only(
                "id", "deletion_requested"
            ).order_by("deletion_requested")[:ob]:
                self.calculate_deletion_component(
                    uc, now, del_expired="only"
                )
        else:
            assert isinstance(ob, get_user_model()), "Not a user model"
            for uc in UserComponent.objects.filter(
                models.Q(deletion_requested__isnull=False) |
                models.Q(contents__deletion_requested__isnull=False),
                user=ob
            ).only(
                "id", "deletion_requested"
            ):
                self.calculate_deletion_component(
                    uc, now, del_expired="only"
                )
        return False


class UserTestMixin(ExpiryMixin, AccessMixin):
    preserved_GET_parameters = {"token", "search", "id", "protection"}
    login_url = reverse_lazy(getattr(
        settings,
        "LOGIN_URL",
        "auth:login"
    ))
    # don't allow AccessMixin to redirect, handle in test_token
    raise_exception = True
    _travel_request = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.request.is_owner = getattr(self.request, "is_owner", False)
        self.request.is_special_user = \
            getattr(self.request, "is_special_user", False)
        self.request.is_staff = getattr(self.request, "is_staff", False)
        self.request.auth_token = getattr(self.request, "auth_token", None)

    def dispatch_extra(self, request, *args, **kwargs):
        return None

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
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

        ret = self.dispatch_extra(  # pylint: disable=W1111
            request,
            *args,
            **kwargs
        )
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
                AssignedContent.travel.get_active_for_request(
                    self.request
                )
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
        ptype = ProtectionType.access_control
        if minstrength >= 4:
            no_token = False
            ptype = ProtectionType.authentication

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
            # after, for having access to token
            self.usercomponent.auth(
                request=self.request, scope=self.scope,
                ptype=ptype, side_effect=True
            )
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
                loggedin_active_tprotections_q
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
        # can use auth token != X-TOKEN
        if user_by_token and self.test_token(4) is True:
            # is_owner, ... set by test_token
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

        margs = {self.user_model.USERNAME_FIELD: None}
        margs[self.user_model.USERNAME_FIELD] = self.kwargs.get("user", None)
        return get_object_or_404(
            self.user_model.objects.select_related("spider_info"),
            **margs
        )

    def get_usercomponent(self) -> UserComponent:
        return get_object_or_404(
            UserComponent.objects.prefetch_related(
                "authtokens"
            ),
            token=self.kwargs["token"]
        )

    def handle_no_permission(self):
        # in case no protections are used (e.g. add content)
        p = getattr(self.request, "protections", False)
        # should be never an integer exclusive False here
        assert \
            p is False or not isinstance(p, int), \
            "handle_no_permission called despite test successful"
        if not p:
            # return 403
            return super().handle_no_permission()
        context = {
            "sanitized_GET": self.sanitize_GET(),
            "LOGIN_URL": self.get_login_url(),
            "scope": getattr(self, "scope", None),
            "uc": self.usercomponent,
            "object": getattr(self, "object", None),
            "is_public_view": self.usercomponent.public
        }
        # check that p is list/tuple/... and not empty
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

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        return super().get_context_data(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # for protections & contents
        return self.get(request, *args, **kwargs)
