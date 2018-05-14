from django.shortcuts import render
from django.views.generic.detail import BaseDetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone

from datetime import timedelta

from .forms import UserComponentCreateForm, UserComponentUpdateForm
from .models import UserComponent, UserContent
from .contents import installed_contents
from .protections import ProtectionType

class UserTestMixin(UserPassesTestMixin):

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

    def has_special_access(self, staff=False, superuser=True):
        if self.request.user == self.get_user():
            return True
        if superuser and self.request.user.is_superuser:
            return True
        if staff and self.request.user.is_staff:
            return True
        return False

    def get_user(self):
        username = None
        if "user" in self.kwargs:
            username = self.kwargs["user"]
        elif self.request.user.is_authenticated:
            username = self.request.user.username
        return get_object_or_404(get_user_model(), username=username)

    def get_usercomponent(self):
        return get_object_or_404(UserComponent, user=self.get_user(), name=self.kwargs["name"])

    #def get_noperm_template_names(self):
    #    return [self.noperm_template_name]

    #def handle_no_permission(self):
    #    raise PermissionDenied(self.get_permission_denied_message())

class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super(UserTestMixin, self).dispatch(request, *args, **kwargs)

class ComponentAllIndex(ListView):
    model = UserComponent
    is_home = False

    def get_context_data(self, **kwargs):
        #kwargs
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        q = models.Q(protected_by__isnull=True)&~models.Q(name="index")
        if self.request.user.is_authenticated:
            q |= models.Q(user=self.request.user)
        if "search" in self.request.GET:
            q &= models.Q(name__icontains=self.request.GET["search"])
        return self.model.objects.filter(q)

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)


class ComponentIndex(UCTestMixin, ListView):
    model = UserComponent

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
        return get_object_or_404(UserComponent, user=self.get_user(), name="index")

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)

class ComponentCreate(PermissionRequiredMixin, UserTestMixin, CreateView):
    model = UserComponent
    permission_required = 'spiderucs.add_usercomponent'
    form_class = UserComponentCreateForm

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        #ret["initial"]["user"] = self.get_user()
        ret["instance"] = self.model(user=self.get_user())
        return ret
class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    form_class = UserComponentUpdateForm

    def get_form_kwargs(self, **kwargs):
        cargs = super().get_form_kwargs(**kwargs)
        if self.request.method == "GET":
            cargs["protection_forms"] = self.object.settings()
        else:
            cargs["protection_forms"] = self.object.settings(self.request.POST)
        return cargs

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        kwargs["assigned"] = self.object.contents.all()
        return super().get_context_data(**kwargs)

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user=self.get_user(), name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user=self.get_user(), name=self.kwargs["name"])

class ComponentDelete(UserTestMixin, DeleteView):
    model = UserComponent
    fields = []
    http_method_names = ['get', 'post', 'delete']

    def get_required_timedelta(self):
        _time = getattr(settings, "UC_DELETION_PERIOD", {}).get(self.object.name, None)
        if not _time:
            _time = getattr(settings, "DEFAULT_DELETION_PERIOD", None)
        if _time:
            now = timezone.now()
            _time = timedelta(seconds=_time)
        return timedelta(seconds=_time)

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        _time = self.get_required_timedelta()
        if _time and self.object.deletion_requested:
            now = timezone.now()
            if self.object.deletion_requested+_time>=now:
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
                if self.object.deletion_requested+_time>=now:
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
            return get_object_or_404(queryset, user=self.get_user(), name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user=self.get_user(), name=self.kwargs["name"])


################################################################################

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
    permission_required = 'add_{}'.format(model._meta.model_name)

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
