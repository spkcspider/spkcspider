__all__ = ("PushTagView",)

from django.http import Http404
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.http.response import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.apps.spider.helpers import get_settings_func, extract_host
from spkcspider.apps.spider.models import (
    AuthToken, AssignedContent
)
from .models import SpiderTag


class PushTagView(UCTestMixin, View):
    model = SpiderTag

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_usercomponent(self):
        token = self.request.GET.get("token", None)
        if not token:
            raise Http404()
        self.request.auth_token = get_object_or_404(
            AuthToken,
            token=token
        )
        return self.request.auth_token.usercomponent

    def test_func(self):
        return True

    def options(self, request, *args, **kwargs):
        ret = super().options()
        ret["Access-Control-Allow-Origin"] = \
            extract_host(self.request.auth_token.referrer)
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.object.config)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        old_size = self.object.get_size()
        oldconfig = self.object.config
        self.object.config = self.request.body.decode(
            "ascii", "backslashreplace"
        )
        # a full_clean is here not required
        self.object.clean()
        try:
            self.object.update_used_space(old_size-self.object.get_size())
        except ValidationError as exc:
            return HttpResponse(
                str(exc), status_code=400
            )
        self.object.save()
        return self.render_to_response(oldconfig)

    def render_to_response(self, config):
        ret = HttpResponse(
            config.encode(
                "ascii", "backslashreplace"
            ), content_type="text/plain"
        )
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = \
            extract_host(self.object.token.referrer)
        return ret
