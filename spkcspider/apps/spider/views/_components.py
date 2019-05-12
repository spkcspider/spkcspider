
__all__ = (
    "ComponentIndex", "ComponentPublicIndex", "ComponentCreate",
    "ComponentUpdate", "ComponentDelete"
)

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404, redirect
from django.db import models
from django.http import HttpResponse, Http404
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext

from rdflib import Graph, Literal, URIRef, XSD

from ._core import UserTestMixin, UCTestMixin, EntityDeletionMixin
from ..constants import spkcgraph
from ..forms import UserComponentForm
from ..queryfilters import (
    filter_contents, filter_components, listed_variants_q
)
from ..models import (
    UserComponent, TravelProtection, AssignedContent
)
from ..helpers import merge_get_url
from ..serializing import paginate_stream, serialize_stream


class ComponentIndexBase(ListView):
    scope = "list"

    def get_context_data(self, **kwargs):
        kwargs["scope"] = self.scope
        return super().get_context_data(**kwargs)

    def get_queryset_components(self, use_contents=True):
        order = None
        if "search" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
        else:
            searchlist = self.request.GET.getlist("search")

        filter_unlisted = not (
                self.request.is_special_user and "_unlisted" in searchlist
            ) and self.scope != "export"
        filter_q, counter = filter_components(
            searchlist, filter_unlisted, use_contents
        )

        if self.request.GET.get("protection", "") == "false":
            filter_q &= models.Q(required_passes=0)

        if self.scope != "export" and "raw" not in self.request.GET:
            order = self.get_ordering(counter > 0)
        ret = self.model.objects.prefetch_related(
            "contents"
        ).filter(filter_q).distinct()
        if order:
            ret = ret.order_by(*order)
        return ret

    def get_queryset_contents(self):
        if "search" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
        else:
            searchlist = self.request.GET.getlist("search")

        filter_unlisted = not (
                self.request.is_special_user and "_unlisted" in searchlist
            ) and self.scope != "export"
        filter_q, counter = filter_contents(
            searchlist, filter_unlisted
        )

        if self.request.GET.get("protection", "") == "false":
            filter_q &= models.Q(required_passes=0)

        return AssignedContent.objects.select_related(
            "usercomponent"
        ).filter(filter_q, strengt__lte=self.source_strength)

    def get_queryset(self):
        if self.request.GET.get("raw") == "embed":
            return self.get_queryset_components(False).filter(
                models.Q(contents__isnull=True) |
                models.Q(strength__gt=self.source_strength)
            )
        else:
            return self.get_queryset_components()

    def get_paginate_by(self, queryset):
        if self.scope == "export" or "raw" in self.request.GET:
            # are later paginated and ordered
            return None
        return settings.SPIDER_OBJECTS_PER_PAGE

    def render_to_response(self, context):
        if self.scope != "export" and "raw" not in self.request.GET:
            return super().render_to_response(context)

        embed = (
            self.scope == "export" or
            self.request.GET.get("raw", "") == "embed"
        )
        session_dict = {
            "request": self.request,
            "context": context,
            "scope": self.scope,
            "expires": None,
            "hostpart": context["hostpart"],
            "uc_namespace": spkcgraph["components"],
            "sourceref": URIRef(context["hostpart"] + self.request.path)
        }

        g = Graph()
        g.namespace_manager.bind("spkc", spkcgraph, replace=True)

        if embed:
            # embed empty components
            per_page = getattr(
                settings,
                "SPIDER_SERIALIZED_PER_PAGE",
                settings.SPIDER_OBJECTS_PER_PAGE
            ) // 2
            p = [
                paginate_stream(
                    self.get_queryset_contents(),
                    per_page,
                    settings.SPIDER_MAX_EMBED_DEPTH
                ),
                paginate_stream(
                    context["object_list"],  # empty components
                    per_page,
                    settings.SPIDER_MAX_EMBED_DEPTH
                )
            ]
        else:
            p = [paginate_stream(
                context["object_list"],
                getattr(
                    settings, "SPIDER_SERIALIZED_PER_PAGE",
                    settings.SPIDER_OBJECTS_PER_PAGE
                ),
                settings.SPIDER_MAX_EMBED_DEPTH
            )]
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass
        if page <= 1:
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(context["scope"], datatype=XSD.string)
            ))
            g.add((
                session_dict["sourceref"], spkcgraph["strength"],
                Literal(self.source_strength)
            ))
            token = getattr(session_dict["request"], "auth_token", None)
            if token:
                token = token.token
            url2 = merge_get_url(str(session_dict["sourceref"]), token=token)
            g.add(
                (
                    session_dict["sourceref"],
                    spkcgraph["action:view"],
                    Literal(url2, datatype=XSD.anyURI)
                )
            )

        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=embed,
            restrict_embed=(self.source_strength == 10),
            restrict_inclusion=(self.source_strength == 10)
        )

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )
        ret["Access-Control-Allow-Origin"] = "*"
        return ret


class ComponentPublicIndex(ComponentIndexBase):
    model = UserComponent
    is_home = False
    source_strength = 0
    preserved_GET_parameters = set(["protection"])

    def dispatch(self, request, *args, **kwargs):
        self.request.is_owner = False
        self.request.is_special_user = False
        self.request.is_staff = False
        self.request.auth_token = None
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = True
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )

        GET = self.request.GET.copy()
        # parameters preserved in search
        for key in list(GET.keys()):
            if key not in self.preserved_GET_parameters:
                GET.pop(key, None)
        kwargs["spider_GET"] = GET
        return super().get_context_data(**kwargs)

    def get_queryset_components(self):
        query = super().get_queryset_components()
        q = models.Q(public=True)
        if self.is_home:
            q &= models.Q(featured=True)

        # doesn't matter if it is same user, lazy
        # only apply unconditional travelprotections here
        travel = TravelProtection.objects.get_active().exclude(
            associated_rel__info__contains="\x1epwhash="
        )
        # remove all travel protected components if not admin or
        # if is is_travel_protected
        if not self.request.is_staff:
            q &= ~models.Q(travel_protected__in=travel)
        return query.filter(q)

    def get_queryset_contents(self):
        query = super().get_queryset_contents()
        q = models.Q(usercomponent__strength=0)
        if self.is_home:
            q &= models.Q(usercomponent__featured=True)
        # doesn't matter if it is same user, lazy
        # only apply unconditional travelprotections here
        travel = TravelProtection.objects.get_active().exclude(
            associated_rel__info__contains="\x1epwhash="
        )
        # remove all travel protected components if not admin or
        # if is is_travel_protected
        if not self.request.is_staff:
            q &= ~models.Q(travel_protected__in=travel)
            q &= ~models.Q(usercomponent__travel_protected__in=travel)
        return query.filter(q)

    def get_ordering(self, issearching=False):
        if not issearching:
            return ("-strength", "-modified",)
        else:
            return ("-strength", "name", "user__username")


class ComponentIndex(UCTestMixin, ComponentIndexBase):
    model = UserComponent
    source_strength = 10

    user = None

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_ordering(self, issearching=False):
        if self.scope == "export":
            return None
        if issearching:
            # MUST use strength here, elsewise travel mode can be exposed
            return ("-strength", "name",)
        return ("-modified",)

    def get_context_data(self, **kwargs):
        kwargs["collection_user"] = self.user
        kwargs["username"] = getattr(self.user, self.user.USERNAME_FIELD)
        kwargs["scope"] = self.scope
        kwargs["is_public_view"] = False
        return super().get_context_data(**kwargs)

    def test_func(self):
        staffperm = {"spider_base.view_usercomponent"}
        if self.scope == "export":
            staffperm.add("spider_base.view_assignedcontent")
        if self.has_special_access(
            user_by_login=True, user_by_token=False,
            staff=staffperm, superuser=True
        ):
            return True
        return False

    def get_queryset_components(self):
        query = super().get_queryset_components().filter(user=self.user)
        # doesn't matter if it is same user, lazy
        travel = self.get_travel_for_request()
        # remove all travel protected components if not admin or
        # if is is_travel_protected
        if not self.request.is_staff:
            query = query.exclude(travel_protected__in=travel)
        return query

    def get_queryset_contents(self):
        query = super().get_queryset_contents().filter(
            usercomponent__user=self.user
        )

        # doesn't matter if it is same user, lazy
        travel = self.get_travel_for_request()
        # remove all travel protected components if not admin or
        # if is is_travel_protected
        if not self.request.is_staff:
            query = query.exclude(travel_protected__in=travel)
            query = query.exclude(usercomponent__travel_protected__in=travel)

        return query

    def get_usercomponent(self):
        return get_object_or_404(
            UserComponent, user=self.user, name="index"
        )


class ComponentCreate(UserTestMixin, CreateView):
    model = UserComponent
    form_class = UserComponentForm

    def dispatch(self, request, *args, **kwargs):
        # can leak elsewise usernames, who have no public components
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied as exc:
            if request.is_staff:
                raise exc
            # elsewise disguise
            raise Http404

    def form_valid(self, form):
        _ = gettext
        messages.success(
            self.request, _('Component created.')
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "spider_base:ucomponent-update", kwargs={
                "token": self.object.token
            }
        )

    def get_usercomponent(self):
        return get_object_or_404(
            UserComponent, user=self.get_user(), name="index"
        )

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["instance"] = self.model(user=self.get_user())
        ret['request'] = self.request
        return ret


class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    form_class = UserComponentForm

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.usercomponent = self.object
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied as exc:
            if request.is_staff:
                raise exc
            # elsewise disguise
            raise Http404

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.has_special_access(
            user_by_login=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        travel = self.get_travel_for_request()
        context["content_variants"] = \
            self.usercomponent.user_info.allowed_content.filter(
                listed_variants_q
            )
        context["content_variants_used"] = \
            context["content_variants"].filter(
                ~models.Q(assignedcontent__travel_protected__in=travel),
                assignedcontent__usercomponent=self.usercomponent
            )
        context["remotelink"] = "{}{}?".format(
            context["hostpart"],
            reverse("spider_base:ucontent-list", kwargs={
                "token": self.usercomponent.token
            })
        )
        return context

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        travel = self.get_travel_for_request()
        return get_object_or_404(
            queryset.prefetch_related(
                "protections",
            ),
            ~models.Q(travel_protected__in=travel),
            token=self.kwargs["token"]
        )

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret['request'] = self.request
        return ret

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'instance': self.object,
            'request': self.request
        }

    def form_valid(self, form):
        _ = gettext
        self.object = form.save()
        persist = 0
        if self.object.primary_anchor:
            persist = self.object.primary_anchor.id
        self.object.authtokens.filter(persist__gte=0).update(
            persist=persist
        )
        if self.kwargs["token"] != self.object.token:
            return redirect(
                "spider_base:ucomponent-update",
                token=self.object.token
            )
        messages.success(self.request, _('Component updated.'))
        return self.render_to_response(
            self.get_context_data(
                form=self.get_form_class()(**self.get_form_success_kwargs())
            )
        )


class ComponentDelete(EntityDeletionMixin, DeleteView):
    model = UserComponent
    fields = []
    object = None

    def form_valid(self, form):
        _ = gettext
        messages.error(
            self.request, _('Component deleted.')
        )
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.usercomponent = self.object
        self.user = self.get_user()
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied as exc:
            if request.is_staff:
                raise exc
            # elsewise disguise
            raise Http404()

    def get_success_url(self):
        username = getattr(self.user, self.user.USERNAME_FIELD)
        return reverse(
            "spider_base:ucomponent-list", kwargs={
                "user": username
            }
        )

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        return super().get_context_data(**kwargs)

    def delete(self, request, *args, **kwargs):
        if self.object.is_index:
            return self.handle_no_permission()
        return super().delete(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.object.is_index:
            return self.handle_no_permission()
        return super().get(request, *args, **kwargs)

    def get_usercomponent(self):
        return self.object

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        travel = self.get_travel_for_request()
        return get_object_or_404(
            queryset, ~models.Q(travel_protected__in=travel),
            token=self.kwargs["token"]
        )
