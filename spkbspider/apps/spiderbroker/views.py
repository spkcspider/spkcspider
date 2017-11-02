from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
import swapper
# Create your views here.
Broker = swapper.load_model("spiderbroker", "Broker")

class BrokerIndex(UserPassesTestMixin, ListView):
    model = Broker

    #def object_list(self):
    #    # TODO: filter
    #    pass

class BrokerDetail(UserPassesTestMixin, DetailView):
    model = Broker

class BrokerCreate(LoginRequiredMixin, CreateView):
    model = Broker
    fields = []

class BrokerDelete(LoginRequiredMixin, DeleteView):
    model = Broker
