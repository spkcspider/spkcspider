from django.shortcuts import render
from django.views.generic.detail import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
import swapper
# Create your views here.
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")


class PublicKeyIndex(ListView):
    model = PublicKey

    #def object_list(self):
    #    # TODO: filter
    #    pass

class PublicKeyDetail(DetailView):
    model = PublicKey

class PublicKeyCreate(CreateView):
    model = PublicKey
    fields = ['note', 'key']

class PublicKeyUpdate(UpdateView):
    model = PublicKey
    fields = ['note', 'key']

class PublicKeyDelete(DeleteView):
    model = PublicKey


class UserComponentIndex(ListView):
    model = UserComponent

    def object_list(self):
        # TODO: filter
        pass

class UserComponentDetail(DetailView):
    model = UserComponent

class UserComponentCreate(CreateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentUpdate(UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']

class UserComponentDelete(DeleteView):
    model = UserComponent
