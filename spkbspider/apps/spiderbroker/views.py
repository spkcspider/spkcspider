from django.shortcuts import render
from django.views.generic.detail import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
# Create your views here.
from .models import Broker

class BrokerIndex(ListView):
    model = Broker

    #def object_list(self):
    #    # TODO: filter
    #    pass

class BrokerDetail(DetailView):
    model = Broker

class BrokerCreate(CreateView):
    model = Broker
    fields = ['note', 'key']

class BrokerDelete(DeleteView):
    model = Broker
