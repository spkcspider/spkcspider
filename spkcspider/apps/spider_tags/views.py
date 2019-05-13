__all__ = ("PushTagView",)

from django.conf import settings
from django.urls import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView

from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import (
    AuthToken
)
from .models import SpiderTag
from .forms import SpiderTagForm


class PushTagView(UCTestMixin, FormView):
    model = SpiderTag
    form_class = SpiderTagForm
    variant = None
    object = None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
        kwargs["user"] = self.usercomponent.user
        return kwargs

    def get_usercomponent(self):
        self.request.auth_token = get_object_or_404(
            AuthToken,
            token=self.request.GET.get("token", None),
            referrer__isnull=False
        )
        return self.request.auth_token.usercomponent

    def test_func(self):
        self.variant = self.usercomponent.features.filter(
            name="PushedTag"
        ).first()
        # can only access feature if activated
        return bool(self.variant)

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = "*"
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def post(self, request, *args, **kwargs):
        # not yet confirmed
        self.object = self.model.static_create(
            token_size=getattr(settings, "TOKEN_SIZE", 30),
            associated_kwargs={
                "usercomponent": self.usercomponent,
                "ctype": self.variant
            }
        )
        # return super().post(request, *args, **kwargs)
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def render_to_response(self, context):
        ret = JsonResponse(
            {
                "layout": [
                    i.name
                    for i in context["form"].fields["layout"].queryset.all()
                ]
            }
        )
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.clean()
        self.object.save()
        form.save_m2m()
        self.object.updateable_by.add(self.request.auth_token.referrer)
        assert(self.object.associated.id)
        assert(self.object.associated.token)
        ret = HttpResponseRedirect(
            redirect_to="{}?token={}".format(
                reverse(
                    "spider_base:ucontent-access",
                    kwargs={
                        "token": self.object.associated.token,
                        "access": "push_update"
                    }
                ),
                self.request.auth_token.token
            )
        )
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret
