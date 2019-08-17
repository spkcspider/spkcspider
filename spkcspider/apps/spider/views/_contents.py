""" Content Views """

__all__ = (
    "ContentIndex", "ContentAdd", "ContentAccess", "ContentDelete",
    "TravelProtectionManagement"
)

from datetime import timedelta
from html import escape

from django.db.models.deletion import ProtectedError
from django.views.generic.edit import DeleteView, UpdateView, CreateView
from django.views.generic.list import ListView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http.response import HttpResponseBase
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.forms.widgets import Media

from next_prev import next_in_order, prev_in_order

from rdflib import Graph, Literal, URIRef, XSD


from ._core import UCTestMixin, EntityDeletionMixin, UserTestMixin
from ._referrer import ReferrerMixin

from ..models import (
    AssignedContent, ContentVariant, UserComponent, TravelProtection
)
from ..forms import UserContentForm, TravelProtectionManagementForm
from ..helpers import get_settings_func, add_property, merge_get_url
from ..queryfilters import (
    filter_contents, listed_variants_q, machine_variants_q
)
from spkcspider.constants import (
    spkcgraph, VariantType, static_token_matcher, loggedin_active_tprotections
)
from ..serializing import paginate_stream, serialize_stream

_forbidden_scopes = frozenset(["add", "list", "raw", "delete", "anchor"])

_extra = '' if settings.DEBUG else '.min'


class ContentBase(UCTestMixin):
    model = AssignedContent
    scope = None
    object = None
    # use token of content object instead
    no_token_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_template_names(self):
        if self.scope in ("add", "update"):
            return ['spider_base/assignedcontent_form.html']
        elif self.scope == "list":
            return ['spider_base/assignedcontent_list.html']
        else:
            return ['spider_base/assignedcontent_access.html']

    def get_ordering(self, issearching=False):
        if self.scope != "list":
            # export: also serializer, other scopes: only one object, overhead
            return None
        # ordering will happen in serializer
        if "raw" in self.request.GET:
            return None
        return ("-priority", "-modified")

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        kwargs["uc"] = self.usercomponent
        kwargs["media"] = Media(
            css={
                "all": [
                    'node_modules/selectize/dist/css/selectize.default.css'
                ]
            },
            js=[
                'node_modules/qrcode-generator/qrcode.js',
                'node_modules/jquery/dist/jquery%s.js' % _extra,
                'node_modules/selectize/dist/js/standalone/selectize%s.js' % _extra  # noqa: E501
            ]
        )
        kwargs["enctype"] = "multipart/form-data"
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        ret = self.model.objects.all()
        # skip search if user and single object
        if self.scope in ("add", "update", "raw_update"):
            return ret

        if getattr(self.request, "auth_token", None):
            idlist = \
                set(self.request.auth_token.extra.get("ids") or [])
            searchlist = \
                self.request.auth_token.extra.get("filter") or []
        else:
            idlist = set()
            searchlist = []

        if self.scope == "list":
            if "search" in self.request.POST or "id" in self.request.POST:
                searchlist += self.request.POST.getlist("search")
                if idlist:
                    idlist.intersection(self.request.POST.getlist("id"))
                else:
                    idlist.update(self.request.POST.getlist("id"))
            else:
                searchlist += self.request.GET.getlist("search")
                if idlist:
                    idlist.intersection(self.request.POST.getlist("id"))
                else:
                    idlist.update(self.request.POST.getlist("id"))
        elif self.scope not in ("add", "update", "raw_update"):
            searchlist += self.request.GET.getlist("search")

        # list only unlisted if explicity requested or export or:
        # if it has high priority (only for special users)
        # listing prioritized, unlisted content is different to the broader
        # search
        filter_unlisted = False
        if self.request.is_special_user:
            # all other scopes than list can show here _unlisted
            # this includes export
            if self.scope == "list" and "_unlisted" not in searchlist:
                filter_unlisted = 0
        else:
            filter_unlisted = True

        filter_q, counter = filter_contents(
            searchlist, idlist, filter_unlisted
        )
        if self.scope == "export":
            ret = ret.exclude(
                ctype__ctype__contains=VariantType.no_export.value
            )

        order = self.get_ordering(counter > 0)
        # distinct required?
        ret = ret.filter(filter_q)
        if order:
            ret = ret.order_by(*order)
        return ret


class ContentIndex(ReferrerMixin, ContentBase, ListView):
    model = AssignedContent
    scope = "list"
    no_token_usercomponent = False
    rate_limit_group = "spider_static_token_error"
    preserved_GET_parameters = {"token", "search", "id"}

    def dispatch_extra(self, request, *args, **kwargs):
        self.allow_domain_mode = ContentVariant.objects.filter(
            feature_for_components=self.usercomponent,
            name="DomainMode"
        ).exists()
        if "referrer" in self.request.GET:
            self.object_list = self.get_queryset()
            return self.handle_referrer()
        return None

    def get_queryset(self):
        travel = self.get_travel_for_request()
        t_ids = travel.values_list("associated_rel__id", flat=True)
        travel = travel.filter(
            login_protection__in=loggedin_active_tprotections
        )
        return super().get_queryset().filter(
            usercomponent=self.usercomponent
        ).exclude(
            models.Q(travel_protected__in=travel) |
            models.Q(id__in=t_ids)
        )

    def get_usercomponent(self):
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )
        q = UserComponent.objects.all()
        if self.request.GET.get("protection", "") == "false":
            q = q.filter(required_passes=0)
        return get_object_or_404(
            q.select_related(
                "user", "user__spider_info",
            ).prefetch_related("protections"),
            ~models.Q(
                travel_protected__in=travel
            ),
            token=self.kwargs["token"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )
        if self.request.is_owner:
            # request.user is maybe anonymous
            context["content_variants"] = \
                self.usercomponent.user.spider_info.allowed_content.filter(
                    listed_variants_q
                )
            context["machine_variants"] = \
                self.usercomponent.user.spider_info.allowed_content.filter(
                    machine_variants_q
                )
            context["content_variants_used"] = \
                context["content_variants"].filter(
                    ~models.Q(assignedcontent__travel_protected__in=travel),
                    assignedcontent__usercomponent=self.usercomponent
                )
        context["active_features"] = self.usercomponent.features.distinct()
        context["active_listed_features"] = \
            context["active_features"].exclude(
                ctype__contains=VariantType.unlisted.value
            )
        context["is_public_view"] = self.usercomponent.public
        context["has_unlisted"] = self.usercomponent.contents.filter(
            info__contains="\x1eunlisted\x1e"
        ).exclude(travel_protected__in=travel).exists()

        context["remotelink"] = "{}{}?".format(
            context["hostpart"],
            reverse("spider_base:ucontent-list", kwargs={
                "token": self.usercomponent.token
            })
        )
        try:
            # mark_safe required for &
            # especially because of mark_safe DON'T remove int()
            context["remotelink_extra"] = mark_safe("page={}&".format(
                int(self.request.GET.get("page", "1"))
            ))
        except ValueError:
            pass
        return context

    def test_func(self):
        staff_perm = not self.usercomponent.is_index
        if staff_perm:
            staff_perm = "spider_base.view_usercomponent"
        # user token is tested later
        # only test if no token is specified
        if not self.request.GET.get("token") and self.has_special_access(
            user_by_login=True, user_by_token=False,
            staff=staff_perm, superuser=True
        ):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_index:
            return False

        # export is only available for user and staff with permission
        minstrength = 0
        if self.scope in ["export"] or self.usercomponent.strength in (4, 9):
            minstrength = 4

        # limit tainted
        ret = self.test_token(minstrength)
        if (
            self.request.auth_token and
            self.request.auth_token.extra.get("taint", False) and
            "referrer" not in self.request.GET
        ):
            return False
        return ret

    def get_paginate_by(self, queryset):
        if self.scope == "export" or "raw" in self.request.GET:
            return None
        return settings.SPIDER_OBJECTS_PER_PAGE

    def render_to_response(self, context):
        if context["scope"] != "export" and "raw" not in self.request.GET:
            return super().render_to_response(context)

        session_dict = {
            "request": self.request,
            "context": context,
            "scope": context["scope"],
            "uc": self.usercomponent,
            "hostpart": context["hostpart"],
            "sourceref": URIRef(context["hostpart"] + self.request.path)
        }
        g = Graph()
        g.namespace_manager.bind("spkc", spkcgraph, replace=True)

        embed = False
        if (
            context["scope"] == "export" or
            self.request.GET.get("raw", "") == "embed"
        ):
            embed = True

        if context["object_list"]:
            p = paginate_stream(
                context["object_list"],
                getattr(
                    settings, "SPIDER_SERIALIZED_PER_PAGE",
                    settings.SPIDER_OBJECTS_PER_PAGE
                ),
                settings.SPIDER_MAX_EMBED_DEPTH
            )
        else:
            # no content, pagination works here only this way
            p = paginate_stream(
                UserComponent.objects.filter(pk=self.usercomponent.pk),
                1,
                1
            )
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass

        if hasattr(self.request, "token_expires"):
            session_dict["expires"] = self.request.token_expires.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )

        if page <= 1:
            # "expires" (string) different from "token_expires" (datetime)
            if session_dict.get("expires"):
                add_property(
                    g, "token_expires", ob=session_dict["request"],
                    ref=session_dict["sourceref"]
                )
            for machinec in context.get("machine_variants", []):
                g.add((
                    session_dict["sourceref"],
                    spkcgraph["create:name"],
                    Literal(machinec, datatype=XSD.string)
                ))
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(context["scope"], datatype=XSD.string)
            ))
            g.add((
                session_dict["sourceref"],
                spkcgraph["type"],
                Literal("Component", datatype=XSD.string)
            ))
            g.add((
                session_dict["sourceref"],
                spkcgraph["strength"],
                Literal(self.usercomponent.strength, datatype=XSD.integer)
            ))
            if context["referrer"]:
                g.add((
                    session_dict["sourceref"],
                    spkcgraph["referrer"],
                    Literal(context["referrer"], datatype=XSD.anyURI)
                ))
            token = getattr(session_dict["request"], "auth_token", None)
            if token:
                token = token.token
            g.add(
                (
                    session_dict["sourceref"],
                    spkcgraph["action:view"],
                    Literal(
                        merge_get_url(
                            str(session_dict["sourceref"]), token=token
                        ),
                        datatype=XSD.anyURI
                    )
                )
            )
            if context["token_strength"]:
                add_property(
                    g, "token_strength", ref=session_dict["sourceref"],
                    literal=context["token_strength"], datatype=XSD.integer
                )
            add_property(
                g, "intentions", ref=session_dict["sourceref"],
                literal=context["intentions"], datatype=XSD.string,
                iterate=True
            )

        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=embed
        )

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )

        if session_dict.get("expires", None):
            ret['X-Token-Expires'] = session_dict["expires"]
        # allow cors requests for raw
        ret["Access-Control-Allow-Origin"] = "*"
        return ret


class ContentAdd(ContentBase, CreateView):
    scope = "add"
    model = ContentVariant
    preserved_GET_parameters = {"token"}

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):
        _ = gettext
        messages.success(
            self.request, _('Content created.')
        )
        return super().form_valid(form)

    def get_queryset(self):
        # use requesting user as base if he can add this type of content
        if self.request.user.is_authenticated:
            return self.request.user.spider_info.allowed_content.filter(
                listed_variants_q |
                models.Q(ctype__contains=VariantType.machine.value)
            )
        else:
            return self.usercomponent.user.spider_info.allowed_content.filter(
                listed_variants_q |
                models.Q(ctype__contains=VariantType.machine.value)
            )

    def test_func(self):
        # test if user and check if user is allowed to create content
        if self.has_special_access(
            user_by_login=True, user_by_token=True, superuser=False
        ):
            if (
                self.request.auth_token and
                self.request.auth_token.extra.get("taint", False)
            ):
                return False
            return True
        return False

    def get_context_data(self, **kwargs):
        kwargs["content_type"] = self.object.installed_class
        kwargs["form"] = self.get_form()
        kwargs["media"] = kwargs["form"].media
        kwargs["active_features"] = self.usercomponent.features.distinct()
        kwargs["active_listed_features"] = \
            kwargs["active_features"].exclude(
                ctype__contains=VariantType.unlisted.value
            )

        kwargs["machine_variants"] = \
            self.usercomponent.user.spider_info.allowed_content.filter(
                machine_variants_q
            )
        return super().get_context_data(**kwargs)

    def get_form(self, allow_data=True):
        assigned = self.object.installed_class.static_create(
            associated_kwargs={
                "usercomponent": self.usercomponent,
                "ctype": self.object
            }
        ).associated
        form_kwargs = {
            "instance": assigned,
            "request": self.request,
            "initial": {
                "usercomponent": self.usercomponent
            }
        }
        if allow_data and self.request.method in ('POST', 'PUT'):
            form_kwargs.update({
                'data': self.request.POST,
                # 'files': self.request.FILES,
            })
        return UserContentForm(**form_kwargs)

    def get_usercomponent(self):
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )
        q = UserComponent.objects.all()
        if self.request.GET.get("protection", "") == "false":
            q = q.filter(required_passes=0)
        return get_object_or_404(
            q.prefetch_related("protections"),
            ~models.Q(travel_protected__in=travel),
            token=self.kwargs["token"],
        )

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        qquery = models.Q(
            name=self.kwargs["type"],
            strength__lte=self.usercomponent.strength
        )
        return get_object_or_404(queryset, qquery)

    def render_to_response(self, context):
        # only true if data
        if context["form"].is_valid():
            ucontent = context["form"].save(commit=False)
        else:
            ucontent = context["form"].instance
        ret = ucontent.content.access(context)

        # return response if content returned response
        if isinstance(ret["content"], HttpResponseBase):
            return ret["content"]
        # redirect if saving worked
        if getattr(ucontent, "id", None):
            assert(ucontent.token)
            assert(ucontent.usercomponent)
            return redirect(
                'spider_base:ucontent-access', permanent=True,
                token=ucontent.token, access="update"
            )
        else:
            assert(not getattr(ucontent.content, "id", None))
        return super().render_to_response(ret)


class ContentAccess(ReferrerMixin, ContentBase, UpdateView):
    scope = "access"
    form_class = UserContentForm
    model = AssignedContent
    rate_limit_group = "spider_static_token_error"
    preserved_GET_parameters = {"token", "search", "id"}

    def dispatch_extra(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.allow_domain_mode = ContentVariant.objects.filter(
            models.Q(feature_for_components=self.usercomponent) |
            models.Q(feature_for_contents=self.object),
            name="DomainMode"
        ).exists()
        # done in get_queryset
        # if getattr(self.request, "auth_token", None):
        #     ids = self.request.auth_token.extra.get("ids", None)
        #     if ids is not None and self.object.id not in ids:
        #         return self.handle_no_permission()
        if "referrer" in self.request.GET:
            self.object_list = self.model.objects.filter(
                pk=self.object.pk
            )
            return self.handle_referrer()

        return None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        _scope = kwargs["access"]
        # special scopes which should be not available as url parameter
        # raw is also deceptive because view and raw=? = raw scope
        if _scope in _forbidden_scopes:
            raise PermissionDenied("Deceptive scopes")
        self.scope = _scope
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = {"form": None}
        if self.scope == "update":
            context["form"] = self.get_form()
        return self.render_to_response(self.get_context_data(**context))

    def post(self, request, *args, **kwargs):
        context = {"form": None}
        # other than update have no form
        if self.scope == "update":
            context["form"] = self.get_form()
            if context["form"].is_valid():
                self.object = context["form"].save(commit=True)
                # use correct usercomponent
                self.usercomponent = context["form"].instance.usercomponent
        return self.render_to_response(self.get_context_data(**context))

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = (
            self.usercomponent.public and
            self.scope not in ("add", "update", "raw_update")
        )

        kwargs["machine_variants"] = \
            self.usercomponent.user.spider_info.allowed_content.filter(
                machine_variants_q
            )
        context = super().get_context_data(**kwargs)

        context["remotelink"] = "{}{}?".format(
            context["hostpart"],
            reverse("spider_base:ucontent-access", kwargs={
                "token": self.object.token,
                "access": "view"
            })
        )
        if self.scope == "update":
            context["active_features"] = self.usercomponent.features.distinct()
        else:
            context["active_features"] = ContentVariant.objects.filter(
                models.Q(feature_for_contents=self.object) |
                models.Q(feature_for_components=self.usercomponent)
            ).distinct()
        context["active_listed_features"] = \
            context["active_features"].exclude(
                ctype__contains=VariantType.unlisted.value
            )
        return context

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'instance': self.object,
            'request': self.request,
            'prefix': self.get_prefix()
        }

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        ret = super().get_form_kwargs()
        ret["request"] = self.request
        return ret

    def test_func(self):
        # give user and staff the ability to update Content
        # except it is index, in this case only the user can update
        # reason: admins could be tricked into malicious updates
        # for index the same reason as for add
        is_index = self.usercomponent.is_index
        staff_perm = not is_index
        if staff_perm:
            staff_perm = "spider_base.view_assignedcontent"
            if self.scope in {"update", "raw_update"}:
                staff_perm = "spider_base.update_assignedcontent"
        # user token is tested later
        # only test if no token is specified
        if not self.request.GET.get("token") and self.has_special_access(
            staff=staff_perm, superuser=(not is_index),
            user_by_token=False, user_by_login=True
        ):
            return True
        if is_index:
            return False
        minstrength = 0
        if (
            self.scope in {"update", "raw_update", "export"} or
            self.usercomponent.strength in (4, 9)
        ):
            minstrength = 4
        ret = self.test_token(minstrength)
        if (
            self.request.auth_token and
            self.request.auth_token.extra.get("taint", False) and
            "referrer" not in self.request.GET
        ):
            return False
        return ret

    def get_usercomponent(self):
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )
        q = UserComponent.objects.all()
        if self.request.GET.get("protection", "") == "false":
            q = q.filter(required_passes=0)
        return get_object_or_404(
            q.prefetch_related("protections"),
            ~models.Q(
                travel_protected__in=travel
            ),
            contents__token=self.kwargs["token"]
        )

    def get_object(self, queryset=None):
        # can bypass idlist and searchlist with own queryset arg
        if not queryset:
            queryset = self.get_queryset()
        # doesn't matter if it is same user, lazy
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )

        # required for next/previous token
        queryset = queryset.select_related(
            "usercomponent", "usercomponent__user",
            "usercomponent__user__spider_info"
        ).filter(usercomponent=self.usercomponent).order_by("priority", "id")
        ob = get_object_or_404(
            queryset,
            (
                ~models.Q(travel_protected__in=travel) |
                models.Q(
                    ctype__name__in={"SelfProtection", "TravelProtection"}
                )
            ),
            token=self.kwargs["token"]
        )
        queryset2 = queryset.exclude(
            ~models.Q(id=ob.id),
            info__contains="\x1eunlisted\x1e",
        )
        ob.previous_object = prev_in_order(ob, queryset2)
        ob.next_object = next_in_order(ob, queryset2)
        # for receiving updates without refresh_from_db
        ob.content.associated_obj = ob
        return ob

    def render_to_response(self, context):
        # context is updated and used outside!!
        ret = self.object.content.access(context)

        # allow contents to redirect from update
        #   (e.g. if user should not know static token)
        if isinstance(ret["content"], HttpResponseBase):
            return ret["content"]
        if self.scope == "update":
            # token changed => path has changed
            if self.object.token != self.kwargs["token"]:
                return redirect(
                    'spider_base:ucontent-access', permanent=True,
                    token=self.object.token, access="update"
                )

            if ret["form"].is_valid():
                ret["form"] = self.get_form_class()(
                    **self.get_form_success_kwargs()
                )

        return super().render_to_response(ret)


class ContentDelete(EntityDeletionMixin, DeleteView):
    model = AssignedContent
    usercomponent = None
    preserved_GET_parameters = {"token", "search", "id"}

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.usercomponent = self.get_usercomponent()
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied as exc:
            if request.is_staff:
                raise exc
            # elsewise disguise
            raise Http404()

    def delete(self, request, *args, **kwargs):
        _ = gettext
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError as exc:
            # hide if travelprotected causes ProtectedError
            travel = self.get_travel_for_request()
            travel = travel.filter(
                models.Q(
                    protect_contents__id__in=exc.protected_objects.values_list(
                        "associated_rel__id", flat=True
                    )
                ) |
                models.Q(
                    protect_components__id__in=exc.protected_objects.values_list(  # noqa: E501
                        "associated_rel__usercomponent__id", flat=True
                    )
                ),
                login_protection__in=loggedin_active_tprotections
            )
            obj = travel.order_by("-start").filter(stop__isnull=True).first()
            if not obj:
                try:
                    obj = travel.latest("stop")
                except travel.model.DoesNotExist:
                    pass
            if obj:
                obj.protect_contents.add(self.object)
                return HttpResponseRedirect(self.get_success_url())
            else:
                messages.error(
                    self.request,
                    mark_safe(
                        _(
                            'Could not delete content dependencies:<br/>{}.'
                        ).format(
                            ",<br/>".join(map(
                                lambda x: escape(repr(x)),
                                exc.protected_objects
                            ))
                        )
                    )
                )
                return self.get(request, *args, **kwargs)

    def form_valid(self, form):
        _ = gettext
        messages.success(
            self.request, _('Content deleted.')
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return reverse(
            "spider_base:ucontent-list", kwargs={
                "token": self.usercomponent.token,
            }
        )

    def test_func(self):
        # can do it over admin panel but for convenience and \
        # allowing users to cancel (in case of timeouts)
        staff_perm = not self.usercomponent.is_index
        if staff_perm:
            staff_perm = "spider_base.delete_assignedcontent"
        ret = self.has_special_access(
            user_by_login=True, user_by_token=True,
            staff=staff_perm, superuser=True
        )
        if (
            self.request.auth_token and
            self.request.auth_token.extra.get("taint", False) and
            "referrer" not in self.request.GET
        ):
            return False
        return ret

    def get_required_timedelta(self):
        _time = self.object.content.deletion_period
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_usercomponent(self):
        return self.object.usercomponent

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )
        return get_object_or_404(
            queryset,
            ~(
                models.Q(travel_protected__in=travel) |
                models.Q(usercomponent__travel_protected__in=travel)
            ),
            token=self.kwargs["token"]
        )


class TravelProtectionManagement(UserTestMixin, UpdateView):
    model = TravelProtection
    template_name = "spider_base/travelprotection.html"
    form_class = TravelProtectionManagementForm

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
        try:
            self.object = self.get_object()
            if not self.object.active:
                messages.success(
                    self.request, _('Protection not active')
                )
                return redirect("home")
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        url = self.request.GET.get("url")
        if url:
            url = static_token_matcher.match(url)
        if not url:
            raise Http404()
        url = url.groupdict()
        return get_object_or_404(
            queryset,
            associated_rel__token=url["static_token"]
        )

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def render_to_response(self, context):
        if not (
            self.object.associated.getflag("anonymous_deactivation") or
            #  not implemented yet
            self.object.associated.getflag("anonymous_trigger")
        ):
            return HttpResponseRedirect(
                redirect_to=self.object.associated.get_absolute_url("update")
            )
        return super().render_to_response(context)

    def form_valid(self, form):
        _ = gettext
        self.object.active = False
        self.object._anonymous_deactivation = \
            self.object.associated.getflag("anonymous_deactivation")
        self.object._encoded_pwhashes = "".join(
            map(
                lambda x: "pwhash={}\x1e".format(x),
                self.object.associated.getlist("pwhash", 20)
            )
        )
        self.object.clean()
        self.object.save(update_fields=["active"])
        messages.success(
            self.request, _('{} disabled').format(self.object.associated.ctype)
        )
        return redirect("home")

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = "*"
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def test_func(self):
        return True
