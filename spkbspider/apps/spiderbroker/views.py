from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse

import swapper
# Create your views here.
Broker = swapper.load_model("spiderbroker", "Broker")

class BrokerAllIndex(ListView):
    model = Broker

    def get_queryset(self):
        return self.model.filter(protected_by=[])


class BrokerIndex(UserPassesTestMixin, ListView):
    model = Broker

    def get_queryset(self):
        return self.model.filter(user__username=self.kwargs["user"])

    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class BrokerDetail(UserPassesTestMixin, DetailView):
    model = Broker
    def test_func(self):
        if self.request.user.is_authenticated:
            return True
        return True

class BrokerCreate(LoginRequiredMixin, CreateView):
    model = Broker
    fields = ['brokertype', 'brokerdata', 'url']

class BrokerUpdate(LoginRequiredMixin, UpdateView):
    model = Broker
    fields = ['protected_by']

class BrokerDelete(LoginRequiredMixin, DeleteView):
    model = Broker
