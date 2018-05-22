__all__ = ("ContentView", "ContentIndex", "ContentAdd", "ContentUpdate", "ContentRemove")


from django.views.generic.detail import BaseDetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.db import models
from django.http import Http404, HttpResponseRedirect
from django.conf import settings

from ._core import UserTestMixin, UCTestMixin
from ._components import ComponentDelete
from ..contents import installed_contents
from ..models import UserContent

from datetime import timedelta

class ContentView(UCTestMixin, BaseDetailView):
    model = UserContent
    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name!="index"), superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_protected:
            return False
        if self.usercomponent.auth_test(self.request, "access"):
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.usercomponent, id=self.kwargs["id"])

    def render_to_response(self, context):
        return self.object.render(**context)

class ContentIndex(UCTestMixin, ListView):
    model = UserContent

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.get_usercomponent()
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=(self.usercomponent.name!="index"), superuser=True):
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_protected:
            return False
        if self.usercomponent.auth_test(self.request, "list"):
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


class ContentAdd(PermissionRequiredMixin, UCTestMixin, CreateView):
    model = UserContent
    permission_required = 'spiderucs.add_usercontent'

    def test_func(self):
        # give user and staff the ability to add Content
        # except it is protected, in this case only the user can add
        # reason: rogue admins could insert false evidence
        uncritically = (self.usercomponent.name not in ["index"])
        if self.has_special_access(staff=uncritically, superuser=uncritically):
            return True
        return False

    def get_form_class(self):
        try:
            return installed_contents[self.kwargs["type"]]
        except KeyError:
            raise Http404('%s matches no available content (hint: blacklisted?)' % self.kwargs["type"])

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["usercomponent"] = self.usercomponent
        return ret

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        content = form.save()
        try:
            info = content.get_info(self.usercomponent)
            if hasattr(form, "get_info"):
                info = "".join([info, form.get_info()])
            self.object = UserContent.objects.create(usercomponent=self.usercomponent, content=content, info=info)
        except Exception as exc:
            content.delete()
            raise exc
        return HttpResponseRedirect(self.get_success_url())

class ContentUpdate(UCTestMixin, UpdateView):
    model = UserContent

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.usercomponent, id=self.kwargs["id"])

    def test_func(self):
        # give user and staff the ability to update Content
        # except it is protected, in this case only the user can update
        # reason: admins could be tricked into malicious updates; for index the same reason as for add
        uncritically = not self.usercomponent.is_protected
        if self.has_special_access(staff=uncritically, superuser=uncritically):
            # block update if noupdate flag is set
            # don't override for special users as the form could trigger unsafe stuff
            # special users: do it in the admin interface
            if self.object.get_flag("noupdate"):
                return False
            return True
        return False

    def get_form_class(self):
        return self.object.content.form_class

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super().get_form_kwargs()
        if hasattr(self, 'object'):
            kwargs.update({'instance': self.object.content})
        return kwargs

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        content = form.save()
        self.object = content.associated
        info = content.get_info(self.usercomponent)
        if hasattr(form, "get_info"):
            info = "".join([info, form.get_info()])
        if info != self.object.info:
            self.object.info = info
            self.object.save(update_fields=["info"])
        return HttpResponseRedirect(self.get_success_url())

class ContentResetRemove(UCTestMixin, UpdateView):
    model = UserContent
    fields = []
    http_method_names = ['post']
    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.usercomponent, id=self.kwargs["id"])
    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.instance
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())


class ContentRemove(ComponentDelete):
    model = UserContent

    def get_required_timedelta(self):
        _time = self.object.get_value("protected_for")
        if not _time and _time>0:
            _time = getattr(settings, "DEFAULT_CONTENT_DELETION_PERIOD", None)
        return timedelta(seconds=_time)

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.get_usercomponent(), id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.get_usercomponent(), id=self.kwargs["id"])
