""" UserContent Views """

__all__ = (
    "ContentIndex", "ContentAdd", "ContentAccess", "ContentRemove"
)

from datetime import timedelta

from django.views.generic.edit import ModelFormMixin
from django.views.generic.list import ListView
from django.views.generic.base import TemplateResponseMixin, View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http.response import HttpResponseBase
from django.http import JsonResponse
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

from ._core import UCTestMixin
from ._components import ComponentDelete
from ..contents import rate_limit_func
from ..constants import UserContentType
from ..models import UserContent, UserContentVariant, UserComponent
from ..forms import UserContentForm


class ContentBase(UCTestMixin):
    model = UserContent
    # Views should use one template to render usercontent (whatever it is)
    template_name = 'spider_base/usercontent_access.html'
    scope = None
    object = None
    no_nonce_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        _scope = kwargs.get("access", None)
        if self.scope == "access":
            # special scopes which should be not available as url parameter
            if _scope in ["add", "list"]:
                raise PermissionDenied("Deceptive scopes")
            self.scope = _scope
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        kwargs["uc"] = self.usercomponent
        kwargs["enctype"] = "multipart/form-data"
        return super().get_context_data(**kwargs)

    def check_write_permission(self):
        # give user and staff the ability to update Content
        # except it is protected, in this case only the user can update
        # reason: admins could be tricked into malicious updates
        # for index the same reason as for add
        uncritically = self.usercomponent.name != "index"
        if self.has_special_access(staff=uncritically, superuser=uncritically):
            return True
        return False

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name != "index"),
                                   superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.name == "index":
            return False
        return self.test_token()


class ContentAccess(ContentBase, ModelFormMixin, TemplateResponseMixin, View):
    scope = "access"
    form_class = UserContentForm
    model = UserContent
    has_write_perm = False

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return rate_limit_func(self, request)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {"form": None}
        if self.scope == "update":
            context["form"] = self.get_form()
        return self.render_to_response(self.get_context_data(**context))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'instance': self.object,
            'prefix': self.get_prefix()
        }

    def test_func(self):
        if self.scope not in ["update", "raw_update"]:
            return super().test_func()
        return self.check_write_permission()

    def render_to_response(self, context):
        if self.scope != "update" or \
           UserContentType.raw_update.value not in self.object.ctype.ctype:
            rendered = self.object.content.render(
                **context
            )
            if UserContentType.raw_update.value in \
               self.object.ctype.ctype:
                return rendered
            # return response if content returned response
            # useful for redirects
            if isinstance(rendered, HttpResponseBase):
                return rendered

            context["content"] = rendered
        if self.scope == "update":
            context["render_in_form"] = True
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
            queryset,
            id=self.kwargs["id"],
            nonce=self.kwargs["nonce"]
        )


class ContentAdd(PermissionRequiredMixin, ContentBase, ModelFormMixin,
                 TemplateResponseMixin, View):
    permission_required = 'spider_base.add_usercontent'
    scope = "add"
    model = UserContentVariant
    also_authenticated_users = True

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def test_func(self):
        self.has_write_perm = self.check_write_permission()
        return self.has_write_perm

    def get_context_data(self, **kwargs):
        kwargs["user_content"] = UserContent(
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
        q_dict = {"name": self.kwargs["type"]}
        if self.usercomponent.name != "index":
            q_dict["ctype__contains"] = UserContentType.public.value
        return get_object_or_404(queryset, **q_dict)

    def render_to_response(self, context):
        ucontent = context.pop("user_content")
        ob = context["content_type"].static_create(
            associated=ucontent, **context
        )
        context["render_in_form"] = True
        rendered = ob.render(**ob.kwargs)

        if UserContentType.raw_add.value in self.object.ctype:
            return rendered
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


class ContentIndex(UCTestMixin, ListView):
    model = UserContent
    scope = "list"
    ordering = ("ctype__name", "id")
    no_nonce_usercomponent = False

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return rate_limit_func(self, request)

    def get_usercomponent(self):
        query = {"id": self.kwargs["id"]}
        query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(UserComponent, **query)

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        if kwargs["uc"].user == self.request.user:
            kwargs["content_types"] = UserContentVariant.objects.all()
            if kwargs["uc"].name != "index":
                kwargs["content_types"] = kwargs["content_types"].exclude(
                    ctype__contains=UserContentType.confidential.value
                )
            if kwargs["uc"].public:
                kwargs["content_types"] = kwargs["content_types"].filter(
                    ctype__contains=UserContentType.public.value
                )
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name != "index"),
                                   superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.name == "index":
            return False

        return self.test_token()

    def get_queryset(self):
        # GET parameters are stronger than post
        ret = super().get_queryset().filter(usercomponent=self.usercomponent)

        filt = models.Q()
        for info in self.request.POST.get("search", "").split(";"):
            if len(info) > 0:
                filt |= models.Q(info__icontains="%s" % info)
        for info in self.request.GET.get("search", "").split(";"):
            if len(info) > 0:
                filt |= models.Q(info__icontains="%s" % info)

        for info in self.request.POST.getlist("info"):
            filt |= models.Q(info__contains=";%s;" % info)
        for info in self.request.GET.getlist("info"):
            filt |= models.Q(info__contains=";%s;" % info)
        return ret.filter(filt)

    def get_paginate_by(self, queryset):
        return getattr(settings, "CONTENTS_PER_PAGE", 25)

    def render_to_response(self, context):
        if self.request.GET.get("raw", "") != "true":
            return super().render_to_response(context)

        ret = {
            "name": self.usercomponent.name,
            "content": [
                {
                    "info": c.info,
                    "link": "?".join(
                        [
                            reverse(
                                "spider_base:ucontent-access",
                                kwargs={
                                    "id": c.id, "nonce": c.nonce,
                                    "access": "view"
                                }
                            ),
                            context["spider_GET"].urlencode()
                        ]
                    )
                } for c in context["object_list"]
            ]
        }
        return JsonResponse(ret)


class ContentRemove(ComponentDelete):
    model = UserContent
    usercomponent = None
    no_nonce_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        return super().dispatch(request, *args, **kwargs)

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
