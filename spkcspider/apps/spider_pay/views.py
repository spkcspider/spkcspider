__all__ = ("SpiderPayView",)

from django.conf import settings
from django.http import Http404
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import models

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

from spkcspider.apps.spider.views import UserTestMixin
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import (
    AuthToken, AssignedContent
)
from .models import Payment


class PaymentsListView(UserTestMixin, View):
    model = Payment

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def test_func(self):
        token = self.request.GET.get("token", None)
        if not token:
            raise Http404()
        self.request.auth_token = get_object_or_404(
            AuthToken,
            token=token
        )
        return "payment" in self.request.auth_token.extra.get(
            "intentions", ()
        )

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = "*"
        ret["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return ret

    def get(self, request, *args, **kwargs):
        hostpart = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        q = models.Q(token=request.auth_token)
        if request.GET.get("also_referrer", "false") == "true":
            q |= models.Q(
                associated_rel__info__contains="\nurl={}\n".format(
                    request.auth_token.referrer.info_url
                )
            )
        ret = JsonResponse(
            {
                "payments": [
                    "{}{}".format(
                        hostpart, i.get_absolute_url()
                    ) for i in Payment.objects.filter(q)
                ]
            }
        )
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = "*"
        return ret
