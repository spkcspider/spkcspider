from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.shortcuts import get_object_or_404


from spkbspider.apps.spider.common import ObjectTestMixin, UserListView, UserDetailView

import swapper
# Create your views here.
Broker = swapper.load_model("spiderbrokers", "Broker")

class BrokerAllIndex(ListView):
    model = Broker

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(associated__usercomponent__user=self.request.user)


class BrokerIndex(UserListView):
    model = Broker

class BrokerDetail(UserDetailView):
    model = Broker

class BrokerCreate(PermissionRequiredMixin, CreateView):
    model = Broker
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['brokertype', 'brokerdata', 'url']

class BrokerUpdate(UserPassesTestMixin, UpdateView):
    model = Broker
    fields = ['protected_by']

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], id=self.kwargs["id"])

class BrokerDelete(UserPassesTestMixin, DeleteView):
    model = Broker
    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], id=self.kwargs["id"])
