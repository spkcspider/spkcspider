from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .forms import UserComponentForm



from .models import UserComponent, UserComponentContent

class ObjectTestMixin(UserPassesTestMixin):
    object = None
    protection = None
    noperm_template_name = "spiderucs/protection_list.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def test_user_has_special_permissions(self):
        if not self.request.user.is_active or not self.request.user.is_authenticated:
            return False
        if self.request.user == self.get_user():
            return True
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        return False

    def get_user(self):
        return self.object.user

    def get_noperm_template_names(self):
        return [self.noperm_template_name]

    def handle_no_permission(self):
        raise PermissionDenied(self.get_permission_denied_message())


class UserComponentAllIndex(ListView):
    model = UserComponent

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class UserComponentIndex(ObjectTestMixin, ListView):
    model = UserComponent

    def test_func(self):
        if self.test_user_has_special_permissions():
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(user__username=self.kwargs["user"])

class UserComponentCreate(PermissionRequiredMixin, CreateView):
    model = UserComponent
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(ObjectTestMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']
    form_class = UserComponentForm

    def get_form_kwargs(self, **kwargs):
        cargs = super().get_form_kwargs(**kwargs)
        cargs["protection_forms"] = self.object.settings()
        return cargs

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], name=self.kwargs["name"])

class UserComponentDelete(ObjectTestMixin, DeleteView):
    model = UserComponent

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], name=self.kwargs["name"])

class ContentIndex(ObjectTestMixin, ListView):
    model = UserComponentContent

    def test_func(self):
        if self.test_user_has_special_permissions():
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(user__username=self.kwargs["user"])
