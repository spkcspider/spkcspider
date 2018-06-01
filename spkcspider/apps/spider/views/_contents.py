""" UserContent Views """

__all__ = (
    "ContentView", "ContentIndex", "ContentAdd", "ContentUpdate",
    "ContentRemove"
)

from datetime import timedelta

from django.views.generic.detail import BaseDetailView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.db import models
from django.conf import settings

from ._core import UCTestMixin
from ._components import ComponentDelete
from ..contents import UserContentType
from ..models import UserContent, UserContentVariant


class ContentBase(UCTestMixin, BaseDetailView):
    model = UserContent
    # Views should use one template to render usercontent (whatever it is)
    template_name = 'spider_base/usercontent_view.html'
    scope = None

    post = BaseDetailView.get
    put = BaseDetailView.get

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name != "index"),
                                   superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_protected:
            return False
        self.request.protections = self.usercomponent.auth(
            request=self.request, scope=self.scope
        )
        if self.request.protections is True:
            return True
        return False

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(queryset,
                                 usercomponent=self.usercomponent,
                                 id=self.kwargs["id"])


class ContentView(ContentBase):
    scope = "view"

    def render_to_response(self, context):
        raw = self.request.GET.get("raw") == "true"
        rendered = self.object.content.render(
            raw=raw, code=self.object.ctype.code, **context
        )
        if raw:
            return rendered
        context["content"] = rendered
        return super().render_to_response(context)


class ContentUpdate(ContentBase):
    scope = "update"

    def test_func(self):
        # give user and staff the ability to update Content
        # except it is protected, in this case only the user can update
        # reason: admins could be tricked into malicious updates
        # for index the same reason as for add
        uncritically = not self.usercomponent.is_protected
        if self.has_special_access(staff=uncritically, superuser=uncritically):
            # block update if noupdate flag is set
            # no override for special users as the form could do unsafe stuff
            # special users: do it in the admin interface
            if self.object.id and self.object.get_flag("noupdate"):
                return False
            return True
        return False

    def render_to_response(self, context):
        rendered = self.object.content.render(
            code=self.object.ctype.code, **context
        )
        if UserContentType.raw_update.value in self.object.ctype.ctype:
            return rendered
        context["content"] = rendered
        return super().render_to_response(context)


class ContentAdd(PermissionRequiredMixin, ContentUpdate):
    permission_required = 'spider_base.add_usercontent'
    scope = "create"
    model = UserContentVariant

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        # FIXME: nil or owner
        q_dict = {
            "name": self.kwargs["type"], "owner"=self.usercomponent.owner
        }
        if self.usercomponent.name != "index":
            q_dict["ctype__contains"] = UserContentType.public.value
        return get_object_or_404(queryset, **q_dict)

    def render_to_response(self, context):
        ob = self.object.installed_class.static_create(
            code=self.object.code, **context
        )
        rendered = ob.render(**ob.kwargs)
        if UserContentType.raw_update.value in self.object.ctype:
            return rendered
        context["content"] = rendered
        return super().render_to_response(context)


class ContentIndex(UCTestMixin, ListView):
    model = UserContent

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.get_usercomponent()
        if kwargs["uc"].user == self.request.user:
            kwargs["content_types"] = UserContentVariant.objects.all()
            if kwargs["uc"].name != "index":
                kwargs["content_types"] = kwargs["content_types"].filter(
                    ctype__contains=UserContentType.public.value
                )
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name != "index"),
                                   superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_protected:
            return False

        self.request.protections = self.usercomponent.auth(
            request=self.request, scope="list"
        )
        if self.request.protections is True:
            return True
        return False

    def get_queryset(self):
        # GET parameters are stronger than post
        ret = self.model.objects.filter(usercomponent=self.usercomponent)

        filt = models.Q()
        for info in self.request.POST.getlist("info"):
            filt |= models.Q(info__contains="%s;" % info)
        for info in self.request.GET.getlist("info"):
            filt |= models.Q(info__contains="%s;" % info)
        ret = ret.filter(filt)
        _type = self.request.POST.get("type", self.request.GET.get("type"))
        if _type:
            ret = ret.filter(info__contains="type=%s;" % _type)
        if "search" in self.request.GET:
            ret = ret.filter(info__icontains=self.request.GET["search"])
        return ret

    def get_paginate_by(self, queryset):
        return getattr(settings, "CONTENTS_PER_PAGE", 25)


class ContentRemove(ComponentDelete):
    model = UserContent

    def get_required_timedelta(self):
        _time = getattr(settings, "CONTENT_DELETION_PERIOD", None)
        if not _time:
            _time = getattr(settings, "DEFAULT_DELETION_PERIOD", None)
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, usercomponent=self.get_usercomponent(),
            id=self.kwargs["id"]
        )
