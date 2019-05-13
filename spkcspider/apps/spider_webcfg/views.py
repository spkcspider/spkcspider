__all__ = ("WebConfigView",)

from django.conf import settings
from django.http import Http404
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.http.response import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import (
    AuthToken, AssignedContent
)
from .models import WebConfig

_empty_set = frozenset()


class WebConfigView(UCTestMixin, View):
    model = WebConfig
    require_persist = True

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "SPIDER_RATELIMIT_FUNC",
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
        if not self.request.auth_token.referrer:
            raise Http404()
        return self.request.auth_token.usercomponent

    def test_func(self):
        return True

    def get_object(self, queryset=None):
        variants = {"TmpConfig"}
        if "persist" in self.request.auth_token.extra.get(
            "intentions", _empty_set
        ):
            variants.add("WebConfig")
        variants = self.usercomponent.features.filter(
            name__in=variants
        )
        if not variants:
            raise Http404()
        try:
            return AssignedContent.objects.from_token(
                token=self.request.auth_token, check_feature=True,
                variant=["WebConfig", "TmpConfig"]
            ).content
        except AssignedContent.DoesNotExist:
            pass
        ret = self.model.static_create(
            token_size=getattr(settings, "TOKEN_SIZE", 30),
            associated_kwargs={
                "usercomponent": self.usercomponent,
                "ctype": "WebConfig",
                "attached_to_token": self.request.auth_token
            }
        )
        ret.clean()
        ret.save()
        assert(ret.associated.token)
        return ret

    def options(self, request, *args, **kwargs):
        ret = super().options()
        self.object = self.get_object()
        ret["Access-Control-Allow-Origin"] = self.object.token.referrer.host
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
        self.object.save(update_fields=["config"])
        return self.render_to_response(oldconfig)

    def render_to_response(self, config):
        ret = HttpResponse(
            config.encode(
                "ascii", "backslashreplace"
            ), content_type="text/plain"
        )
        ret["X-SPIDER-URL"] = self.request.auth_token.referrer.url
        ret["X-SPIDER-MODIFIED"] = self.object.associated.modified
        ret["X-SPIDER-CREATED"] = self.object.associated.created
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret
