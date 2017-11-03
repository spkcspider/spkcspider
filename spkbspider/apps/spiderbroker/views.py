from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse


from spkbspider.common import ObjectTestMixin

import swapper
# Create your views here.
Broker = swapper.load_model("spiderbroker", "Broker")
UserComponent = swapper.load_model("spiderpk", "UserComponent")

class BrokerAllIndex(ListView):
    model = Broker

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))


class BrokerIndex(UserPassesTestMixin, ListView):
    model = Broker

    def get_queryset(self):
        return self.model.filter(user__username=self.kwargs["user"])

    def test_func(self):
        if self.request.user == self.object.user:
            return True
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return True
        uc = UserComponent.objects.get_or_create(user=self.request.user, name="broker")
        return uc.validate(self.request)

class BrokerDetail(UserPassesTestMixin, DetailView):
    model = Broker
    def test_func(self):
        if self.request.user == self.user:
            return True
        return True

    def get_object(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], id=self.kwargs["id"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], id=self.kwargs["id"])

class BrokerCreate(PermissionRequiredMixin, CreateView):
    model = Broker
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['brokertype', 'brokerdata', 'url']

class BrokerUpdate(UserPassesTestMixin, UpdateView):
    model = Broker
    fields = ['protected_by']
    # only owner can update
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False
    def get_object(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], id=self.kwargs["id"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], id=self.kwargs["id"])

class BrokerDelete(UserPassesTestMixin, DeleteView):
    model = Broker
    # only owner can delete
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return queryset.get(user__username=self.kwargs["user"], id=self.kwargs["id"])
        else:
            return self.model.objects.get(user__username=self.kwargs["user"], id=self.kwargs["id"])
