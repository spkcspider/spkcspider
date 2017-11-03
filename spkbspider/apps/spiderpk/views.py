from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.base import RedirectView
from django.urls import reverse

import swapper
# Create your views here.
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")

class RedirectUserPK(RedirectView):
    permanent = False
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse("spiderpk:pk-list", kwargs={"user":self.request.user.username})
        else:
            return "/"

class RedirectUserUC(RedirectView):
    permanent = False
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse("spiderpk:uc-list", kwargs={"user":self.request.user.username})
        else:
            return "/"

class PublicKeyAllIndex(ListView):
    model = PublicKey

    def get_queryset(self):
        return self.model.filter(protected_by=[])

class PublicKeyIndex(UserPassesTestMixin, ListView):
    model = PublicKey

    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class PublicKeyDetail(UserPassesTestMixin, DetailView):
    model = PublicKey
    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class PublicKeyCreate(LoginRequiredMixin, CreateView):
    model = PublicKey
    fields = ['note', 'key']

class PublicKeyUpdate(LoginRequiredMixin, UpdateView):
    model = PublicKey
    fields = ['note', 'key', 'protected_by']

class PublicKeyDelete(LoginRequiredMixin, DeleteView):
    model = PublicKey

class UserComponentAllIndex(ListView):
    model = UserComponent

    def get_queryset(self):
        return self.model.filter(protected_by=[])

class UserComponentIndex(UserPassesTestMixin, ListView):
    model = UserComponent

    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class UserComponentDetail(UserPassesTestMixin, DetailView):
    model = UserComponent

    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class UserComponentCreate(LoginRequiredMixin, CreateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(LoginRequiredMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentDelete(LoginRequiredMixin, DeleteView):
    model = UserComponent
