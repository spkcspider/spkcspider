__all__ = ("SpiderSerializeUser", )

from django.shortcuts import get_object_or_404
from django.views.generic.base import View
from django.db import models

from ._core import UserTestMixin
from ..models import UserComponent


class SpiderSerializeUser(UserTestMixin, View):
    also_authenticated_users = True

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        self.usercomponent = self.get_usercomponent()
        return super().dispatch(request, *args, **kwargs)

    def get_usercomponent(self):
        query = {"name": self.kwargs.get("name", "index")}
        query["user"] = self.user
        if "name" in self.kwargs:
            query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(UserComponent, **query)

    def get_queryset(self):
        qfilter = models.Q()
        if "name" in self.kwargs:
            qfilter &= models.Q(name=self.kwargs["name"])
        return self.user.usercomponents.filter(qfilter)
