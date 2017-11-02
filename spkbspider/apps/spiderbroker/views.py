from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
import swapper
# Create your views here.
Broker = swapper.load_model("spiderbroker", "Broker")

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
