from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic.base import RedirectView
from django.urls import reverse

import swapper

from spkbspider.common import ObjectTestMixin

# Create your views here.
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")

class PublicKeyAllIndex(ListView):
    model = PublicKey

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class PublicKeyIndex(UserPassesTestMixin, ListView):
    model = PublicKey

    def test_func(self):
        if self.request.user.username == self.kwargs["user"]:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = UserComponent.objects.get_or_create(user=self.request.user, name="publickeys")
        return uc.validate(self.request)

class PublicKeyDetail(ObjectTestMixin, DetailView):
    model = PublicKey
    def test_func(self):
        if not self.object:
            return True
        if self.request.user == self.object.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = UserComponent.objects.get_or_create(user=self.request.user, name="publickeys")
        return uc.validate(self.request)

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.filter(user__username=self.kwargs["user"], hash=self.kwargs["hash"]).first()
        else:
            return self.model.objects.filter(user__username=self.kwargs["user"], hash=self.kwargs["hash"]).first()


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

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], hash=self.kwargs["hash"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], hash=self.kwargs["hash"])

class PublicKeyDelete(ObjectTestMixin, DeleteView):
    model = PublicKey
    # only owner can delete
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], hash=self.kwargs["hash"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], hash=self.kwargs["hash"])

class UserComponentAllIndex(ListView):
    model = UserComponent

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class UserComponentIndex(UserPassesTestMixin, ListView):
    model = UserComponent

    def test_func(self):
        if self.request.user == self.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = self.objects.get_or_create(user=self.request.user, name="identity")
        return uc.validate(self.request)

class UserComponentDetail(ObjectTestMixin, DetailView):
    model = UserComponent

    def test_func(self):
        if self.request.user == self.object.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        return self.validate(self.request)

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], hash=self.kwargs["name"])

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

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], hash=self.kwargs["name"])


class UserComponentDelete(ObjectTestMixin, DeleteView):
    model = UserComponent
    # only owner can delete
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object2(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], name=self.kwargs["name"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], hash=self.kwargs["name"])
