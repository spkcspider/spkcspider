
__all__ = (
    "ComponentIndex", "ComponentAllIndex", "ComponentCreate",
    "ComponentUpdate", "ComponentDelete"
)

from datetime import timedelta

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.db import models
from django.http import HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ._core import UserTestMixin, UCTestMixin
from ..forms import UserComponentForm
from ..contents import installed_contents
from ..models import UserComponent


class ComponentAllIndex(ListView):
    model = UserComponent
    is_home = False
    _base_query = ~models.Q(name="index") | models.Q(protections__code="allow")
    _base_query2 = models.Q(len_prot=1)

    def get_queryset(self):
        q = self._base_query
        q2 = self._base_query2
        if self.request.user.is_authenticated:
            q2 |= models.Q(user=self.request.user)
        if "search" in self.request.GET:
            q &= models.Q(name__icontains=self.request.GET["search"])
        return self.model.objects.filter(q).annotate(
            len_prot=models.Count('protections')
        ).filter(q2)

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)


class ComponentIndex(UCTestMixin, ListView):
    model = UserComponent

    def get_context_data(self, **kwargs):
        kwargs["component_user"] = self.get_user()
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=True):
            return True
        return False

    def get_queryset(self):
        ret = self.model.objects.filter(user=self.get_user())
        if "search" in self.request.GET:
            ret = ret.filter(name__icontains=self.request.GET["search"])
        return ret

    def get_usercomponent(self):
        return get_object_or_404(
            UserComponent, user=self.get_user(), name="index"
        )

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)


class ComponentCreate(PermissionRequiredMixin, UserTestMixin, CreateView):
    model = UserComponent
    permission_required = 'spider_base.add_usercomponent'
    form_class = UserComponentForm

    def get_success_url(self):
        return reverse(
            "spider_base:ucomponent-update", kwargs={"name": self.object.name}
        )

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["instance"] = self.model(user=self.get_user())
        return ret


class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    form_class = UserComponentForm

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, user=self.get_user(), name=self.kwargs["name"]
        )

    def form_valid(self, form):
        self.object = form.save()
        return self.render_to_response(
            self.get_context_data(form=self.get_form())
        )


class ComponentDelete(UserTestMixin, DeleteView):
    model = UserComponent
    fields = []
    object = None
    http_method_names = ['get', 'post', 'delete']

    def get_required_timedelta(self):
        _time = getattr(settings, "COMPONENT_DELETION_PERIOD", None)
        if not _time:
            _time = getattr(settings, "DEFAULT_DELETION_PERIOD", None)
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        _time = self.get_required_timedelta()
        if _time and self.object.deletion_requested:
            now = timezone.now()
            if self.object.deletion_requested + _time >= now:
                kwargs["remaining"] = timedelta(seconds=0)
            else:
                kwargs["remaining"] = self.object.deletion_requested+_time-now
        return super().get_context_data(**kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # deleting them should not be possible, except by deleting user
        if self.object.is_protected:
            return self.handle_no_permission()
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
        self.object = self.get_object()
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(
                queryset, user=self.get_user(), name=self.kwargs["name"]
            )
        else:
            return get_object_or_404(
                self.get_queryset(), user=self.get_user(),
                name=self.kwargs["name"]
            )
