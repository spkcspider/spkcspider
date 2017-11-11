from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic.base import RedirectView
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

import swapper

from spkbspider.common import ObjectTestMixin, UserListView, UserDetailView

# Create your views here.
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")

class PublicKeyAllIndex(ListView):
    model = PublicKey

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class PublicKeyIndex(UserListView):
    model = PublicKey

class PublicKeyDetail(UserDetailView):
    model = PublicKey

class PublicKeyCreate(PermissionRequiredMixin, CreateView):
    model = PublicKey
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['note', 'key']

class PublicKeyUpdate(ObjectTestMixin, UpdateView):
    model = PublicKey
    fields = ['note', 'key', 'protected_by']
    # only owner can update
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], hash=self.kwargs["hash"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], hash=self.kwargs["hash"])

class PublicKeyDelete(ObjectTestMixin, DeleteView):
    model = PublicKey
    # only owner can delete
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], hash=self.kwargs["hash"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], hash=self.kwargs["hash"])

class UserComponentAllIndex(ListView):
    model = UserComponent

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class UserComponentIndex(UserListView):
    model = UserComponent

class UserComponentDetail(UserDetailView):
    model = UserComponent

class UserComponentCreate(PermissionRequiredMixin, CreateView):
    model = UserComponent
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(ObjectTestMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']
    # only owner can update
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], hash=self.kwargs["name"])


class UserComponentDelete(ObjectTestMixin, DeleteView):
    model = UserComponent
    # only owner can delete
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], hash=self.kwargs["name"])
