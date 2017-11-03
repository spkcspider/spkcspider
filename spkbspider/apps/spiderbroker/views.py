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

    def get_queryset(self):
        return self.model.filter(user__username=self.kwargs["user"])

    def test_func(self):
        return True

class BrokerDetail(UserPassesTestMixin, DetailView):
    model = Broker
    def test_func(self):
        return True

class BrokerCreate(LoginRequiredMixin, CreateView):
    model = Broker
    fields = []
    def test_func(self):
        return True

class BrokerDelete(LoginRequiredMixin, DeleteView):
    model = Broker
    def test_func(self):
        return True
