""" UserContent Views """

__all__ = (
    "ContentIndex", "ContentAdd", "ContentAccess", "ContentRemove"
)

from datetime import timedelta

from django.views.generic.edit import ProcessFormView, ModelFormMixin
from django.views.generic.list import ListView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied

from ._core import UCTestMixin
from ._components import ComponentDelete
from ..contents import UserContentType
from ..models import UserContent, UserContentVariant
from ..forms import UserContentForm


class ContentBase(UCTestMixin):
    model = UserContent
    # Views should use one template to render usercontent (whatever it is)
    template_name = 'spider_base/usercontent_access.html'
    scope = None

    def dispatch(self, request, *args, **kwargs):
        _scope = kwargs.get("access", None)
        if self.scope == "access":
            if _scope in ["update", "add", "list"]:
                raise PermissionDenied("Deceptive scopes")
            self.scope = _scope
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        return super().get_context_data(**kwargs)

    def check_write_permission(self):
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


class ContentAccess(ModelFormMixin, ProcessFormView, ContentBase):
    scope = "access"
    form_class = UserContentForm
    has_write_perm = False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {"form": None}
        if self.scope in ["update"]:
            context["form"] = self.get_form()
        return self.render_to_response(self.get_context_data(context))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {"form": None}
        if self.scope in ["update"]:
            context["form"] = self.get_form()
            if context["form"].is_valid():
                self.object = context["form"].save()
                context["form"] = self.get_form_class()(
                    **self.get_form_success_kwargs()
                )
        return self.render_to_response(self.get_context_data(context))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["disabled"] = not self.check_write_permission()
        return kwargs

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'disabled': not self.check_write_permission()
        }

    def test_func(self):
        if self.scope not in ["update", "raw_update", "add"]:
            return super().test_func()
        self.has_write_perm = self.check_write_permission()
        return self.has_write_perm

    def render_to_response(self, context):
        if UserContentType.raw_update.value not in self.object.ctype.ctype or \
           self.scope not in ["update", "add"]:
            rendered = self.object.content.render(
                **context
            )
            if UserContentType.raw_update.value in self.object.ctype.ctype:
                return rendered

            context["content"] = rendered
        return super().render_to_response(context)

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(queryset,
                                 accessid=self.kwargs["id"])


class ContentAdd(PermissionRequiredMixin, ContentAccess):
    permission_required = 'spider_base.add_usercontent'
    scope = "add"
    model = UserContentVariant

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        queryset = queryset.filter(
            models.Q(owner=self.usercomponent) | models.Q(owner__isnull=True)
        )
        q_dict = {"name": self.kwargs["type"]}
        if self.usercomponent.name != "index":
            q_dict["ctype__contains"] = UserContentType.public.value
        return get_object_or_404(queryset, **q_dict)

    def render_to_response(self, context):
        ob = self.object.installed_class.static_create(
            associated=self.object, **context
        )
        if UserContentType.raw_update.value not in self.object.ctype or \
           self.scope not in ["update", "add"]:
                rendered = ob.render(**ob.kwargs)
                if UserContentType.raw_update.value in self.object.ctype:
                    return rendered
                context["content"] = rendered
        return super().render_to_response(context)


class ContentIndex(UCTestMixin, ListView):
    model = UserContent
    scope = "list"
    ordering = ("associated__ctype__name", "id")

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
            findid=self.kwargs["id"]
        )
