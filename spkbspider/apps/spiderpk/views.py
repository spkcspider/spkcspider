from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

import swapper
# Create your views here.
UserComponent = None #swapper.load_model("spiderpk", "UserComponent")
PublicKey = None #swapper.load_model("spiderpk", "PublicKey")


class PublicKeyIndex(UserPassesTestMixin, ListView):
    model = PublicKey

    #def object_list(self):
    #    # TODO: filter
    #    pass

class PublicKeyDetail(UserPassesTestMixin, DetailView):
    model = PublicKey

class PublicKeyCreate(LoginRequiredMixin, CreateView):
    model = PublicKey
    fields = ['note', 'key']

class PublicKeyUpdate(LoginRequiredMixin, UpdateView):
    model = PublicKey
    fields = ['note', 'key']

class PublicKeyDelete(LoginRequiredMixin, DeleteView):
    model = PublicKey


class UserComponentIndex(UserPassesTestMixin, ListView):
    model = UserComponent

    def object_list(self):
        # TODO: filter
        pass

class UserComponentDetail(UserPassesTestMixin, DetailView):
    model = UserComponent

class UserComponentCreate(LoginRequiredMixin, CreateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(LoginRequiredMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentDelete(LoginRequiredMixin, DeleteView):
    model = UserComponent
