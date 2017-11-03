from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic.base import RedirectView
from django.urls import reverse

import swapper
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
        if self.request.user == self.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = UserComponent.objects.get_or_create(user=self.request.user, name="publickeys")
        return uc.validate(self.request)

class PublicKeyDetail(UserPassesTestMixin, DetailView):
    model = PublicKey
    def test_func(self):
        if self.request.user == self.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = UserComponent.objects.get_or_create(user=self.request.user, name="publickeys")
        return uc.validate(self.request)

class PublicKeyCreate(PermissionRequiredMixin, CreateView):
    model = PublicKey
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['note', 'key']

class PublicKeyUpdate(LoginRequiredMixin, UpdateView):
    model = PublicKey
    fields = ['note', 'key', 'protected_by']

class PublicKeyDelete(LoginRequiredMixin, DeleteView):
    model = PublicKey

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

class UserComponentDetail(UserPassesTestMixin, DetailView):
    model = UserComponent

    def test_func(self):
        if self.request.user == self.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        return self.validate(self.request)

class UserComponentCreate(PermissionRequiredMixin, CreateView):
    model = UserComponent
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(UserPassesTestMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentDelete(UserPassesTestMixin, DeleteView):
    model = UserComponent
