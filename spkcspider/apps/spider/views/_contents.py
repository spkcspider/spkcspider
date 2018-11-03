""" Content Views """

__all__ = (
    "ContentIndex", "ContentAdd", "ContentAccess", "ContentRemove"
)
from datetime import timedelta

from django.views.generic.edit import ModelFormMixin
from django.views.generic.list import ListView
from django.views.generic.base import TemplateResponseMixin, View
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http.response import HttpResponseBase, HttpResponse
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404


from rdflib import Graph, Literal, URIRef


from ._core import UCTestMixin, UserTestMixin
from ._components import ComponentDelete
from ..models import (
    AssignedContent, ContentVariant, UserComponent
)
from ..forms import UserContentForm
from ..helpers import get_settings_func
from ..constants import namespaces_spkcspider
from ..serializing import paginated_contents, serialize_stream


class ContentBase(UCTestMixin):
    model = AssignedContent
    scope = None
    object = None
    no_nonce_usercomponent = True

    def get_template_names(self):
        if self.scope in ("add", "update"):
            return ['spider_base/assignedcontent_form.html']
        else:
            return ['spider_base/assignedcontent_access.html']

    def dispatch(self, request, *args, **kwargs):
        _scope = kwargs.get("access", None)
        if self.scope == "access":
            # special scopes which should be not available as url parameter
            # raw is also deceptive because view and raw=? = raw scope
            if _scope in ["add", "list", "raw"]:
                raise PermissionDenied("Deceptive scopes")
            self.scope = _scope
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        kwargs["uc"] = self.usercomponent
        kwargs["enctype"] = "multipart/form-data"
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name != "index"),
                                   superuser=True):
            self.request.auth_token = self.create_admin_token()
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.name == "index":
            return False
        return self.test_token()


class ContentAccess(ContentBase, ModelFormMixin, TemplateResponseMixin, View):
    scope = "access"
    form_class = UserContentForm
    model = AssignedContent

    def dispatch(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

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
                self.object = context["form"].save()
                # nonce changed => path has changed
                if self.object.nonce != self.kwargs["nonce"]:
                    return redirect(
                        'spider_base:ucontent-access',
                        id=self.object.id,
                        nonce=self.object.nonce, access="update"
                    )
                context["form"] = self.get_form_class()(
                    **self.get_form_success_kwargs()
                )
        return self.render_to_response(self.get_context_data(**context))

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = (
            self.usercomponent.public and
            self.scope not in ("add", "update", "update_raw")
        )
        context = super().get_context_data(**kwargs)

        if self.scope != "add":
            context["remotelink"] = context["spider_GET"].copy()
            if self.request.auth_token:
                context["remotelink"]["token"] = \
                    self.request.auth_token.token
                context["remotelink"].pop("prefer_get", None)
            context["remotelink"] = "{}{}?{}".format(
                context["hostpart"],
                reverse("spider_base:ucontent-access", kwargs={
                    "id": self.object.id,
                    "nonce": self.object.nonce,
                    "access": "view"
                }),
                context["remotelink"].urlencode()
            )
        return context

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'instance': self.object,
            'prefix': self.get_prefix()
        }

    def test_func(self):
        if self.scope not in ["update", "raw_update", "export"]:
            return super().test_func()
        # give user and staff the ability to update Content
        # except it is protected, in this case only the user can update
        # reason: admins could be tricked into malicious updates
        # for index the same reason as for add
        uncritically = self.usercomponent.name != "index"
        if self.has_special_access(staff=uncritically, superuser=uncritically):
            self.request.auth_token = self.create_admin_token()
            return True
        return False

    def render_to_response(self, context):
        rendered = self.object.content.render(
            **context
        )
        # return response if content returned response
        # useful for redirects and raw update
        if isinstance(rendered, HttpResponseBase):
            return rendered

        context["content"] = rendered
        return super().render_to_response(context)

    def get_usercomponent(self):
        if self.object:
            return self.object.usercomponent
        return self.get_object().usercomponent

    def get_user(self):
        return self.usercomponent.user

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset.select_related(
                "usercomponent", "usercomponent__user",
                "usercomponent__user__spider_info"
            ),
            id=self.kwargs["id"],
            nonce=self.kwargs["nonce"]
        )


class ContentIndex(UCTestMixin, ListView):
    model = AssignedContent
    scope = "list"
    ordering = ("id",)
    no_nonce_usercomponent = False

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_usercomponent(self):
        query = {"id": self.kwargs["id"]}
        query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(
            UserComponent.objects.select_related(
                "user", "user__spider_info",
            ).prefetch_related("protections"),
            **query
        )

    def get_context_data(self, **kwargs):
        kwargs["scope"] = self.scope
        kwargs["uc"] = self.usercomponent
        context = super().get_context_data(**kwargs)
        if self.usercomponent.user == self.request.user:
            context["content_variants"] = (
                self.usercomponent.user_info.allowed_content.all()
            )
        context["is_public_view"] = self.usercomponent.public

        context["remotelink"] = context["spider_GET"].copy()
        if self.request.auth_token:
            context["remotelink"]["token"] = \
                self.request.auth_token.token
            context["remotelink"].pop("prefer_get", None)
        context["remotelink"] = "{}{}?{}".format(
            context["hostpart"],
            reverse("spider_base:ucontent-list", kwargs={
                "id": self.usercomponent.id,
                "nonce": self.usercomponent.nonce
            }),
            context["remotelink"].urlencode()
        )
        return context

    def test_func(self):
        if self.has_special_access(
            staff=(not self.usercomponent.is_index),
            superuser=True
        ):
            self.request.auth_token = self.create_admin_token()
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_index:
            return False
        # export is only available for user and superuser
        if self.scope == "export":
            # if self.request.user.is_staff:
            #     return True
            return False

        return self.test_token()

    def get_queryset(self):
        ret = super().get_queryset().filter(usercomponent=self.usercomponent)

        searchq = models.Q()
        searchq_exc = models.Q()
        infoq = models.Q()
        infoq_exc = models.Q()

        counter = 0
        # against ddos
        max_counter = getattr(settings, "MAX_SEARCH_PARAMETERS", 30)

        if "search" in self.request.POST or "info" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
            infolist = self.request.POST.getlist("info")
            idlist = self.request.POST.getlist("id")
        else:
            searchlist = self.request.GET.getlist("search")
            infolist = self.request.GET.getlist("info")
            idlist = self.request.GET.getlist("id")

        for item in searchlist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                searchq |= models.Q(
                    info__icontains="%s" % item[1:]
                )
            elif item.startswith("!"):
                searchq_exc |= models.Q(
                    info__icontains="%s" % item[1:]
                )
            else:
                searchq |= models.Q(
                    info__icontains="%s" % item
                )

        for item in infolist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue

            if item.startswith("!!"):
                infoq |= models.Q(info__contains="\n%s\n" % item[1:])
            elif item.startswith("!"):
                infoq_exc |= models.Q(
                    info__contains="\n%s\n" % item[1:]
                )
            else:
                infoq |= models.Q(info__contains="\n%s\n" % item)
        if idlist:
            ids = map(lambda x: int(x), idlist)
            searchq &= (models.Q(id__in=ids) | models.Q(fake_id__in=ids))

        return ret.filter(searchq & infoq & ~searchq_exc & ~infoq_exc)

    def get_paginate_by(self, queryset):
        if self.scope == "export" or "raw" in self.request.GET:
            return None
        return getattr(settings, "CONTENTS_PER_PAGE", 25)

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
        namesp_meta = namespaces_spkcspider.meta
        g = Graph()

        embed = False
        if (
            context["scope"] == "export" or
            self.request.GET.get("raw", "") == "embed"
        ):
            embed = True

        p = paginated_contents(
            context["object_list"],
            getattr(settings, "SERIALIZED_PER_PAGE", 50)
        )
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass
        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=embed
        )

        if hasattr(self.request, "token_expires"):
            session_dict["expires"] = self.request.token_expires.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )
            if page <= 1:
                g.add((
                    session_dict["sourceref"],
                    namesp_meta.expires,
                    Literal(self.request.token_expires)
                ))
        if page <= 1:
            g.add((
                session_dict["sourceref"],
                namesp_meta.scope,
                Literal(context["scope"])
            ))

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )

        if session_dict.get("expires", None):
            ret['X-Token-Expires'] = session_dict["expires"]
        return ret


class ContentAdd(ContentBase, ModelFormMixin,
                 TemplateResponseMixin, View):
    scope = "add"
    model = ContentVariant
    also_authenticated_users = True

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def test_func(self):
        # test if user and check if user is allowed to create content
        if (
            self.has_special_access(user=True, superuser=False) and
            self.usercomponent.user_info.allowed_content.filter(
                name=self.kwargs["type"]
            ).exists()
        ):
            return True
        return False

    def get_context_data(self, **kwargs):
        kwargs["user_content"] = AssignedContent(
            usercomponent=self.usercomponent,
            ctype=self.object
        )
        kwargs["content_type"] = self.object.installed_class
        form_kwargs = {
            "instance": kwargs["user_content"],
            "initial": {
                "usercomponent": self.usercomponent
            }
        }
        if self.request.method in ('POST', 'PUT'):
            form_kwargs.update({
                'data': self.request.POST,
                # 'files': self.request.FILES,
            })
        kwargs["form"] = UserContentForm(**form_kwargs)
        return super().get_context_data(**kwargs)

    def get_form(self):
        # should never be called
        raise NotImplementedError

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        qquery = models.Q(
            name=self.kwargs["type"],
            strength__lte=self.usercomponent.strength
        )
        return get_object_or_404(queryset, qquery)

    def render_to_response(self, context):
        ucontent = context.pop("user_content")
        ob = context["content_type"].static_create(
            associated=ucontent, **context
        )
        rendered = ob.render(**ob.kwargs)

        # return response if content returned response
        if isinstance(rendered, HttpResponseBase):
            return rendered
        # show framed output
        context["content"] = rendered
        # redirect if saving worked
        if getattr(ob, "id", None):
            assert(hasattr(ucontent, "id") and ucontent.usercomponent)
            return redirect(
                'spider_base:ucontent-access', id=ucontent.id,
                nonce=ucontent.nonce, access="update"
            )
        return super().render_to_response(context)


class ContentRemove(ComponentDelete):
    model = AssignedContent
    usercomponent = None
    no_nonce_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        self.user = self.usercomponent.user
        self.object = self.get_object()
        return UserTestMixin.dispatch(self, request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "spider_base:ucontent-list", kwargs={
                "id": self.usercomponent.id,
                "nonce":  self.usercomponent.nonce
            }
        )

    def get_required_timedelta(self):
        _time = self.object.content.deletion_period
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, usercomponent=self.usercomponent,
            id=self.kwargs["id"], nonce=self.kwargs["nonce"]
        )
