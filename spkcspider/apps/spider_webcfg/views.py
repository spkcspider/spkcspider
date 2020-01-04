__all__ = ("WebConfigView",)

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from spkcspider.apps.spider.models import (
    AssignedContent, AttachedBlob, AuthToken
)
from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.utils.settings import get_settings_func

from .models import WebConfig

_empty_set = frozenset()
tmpconfig_max = 1024


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
            )(request, self)

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
        if self.request.auth_token.persist >= 0:
            variants.add("WebConfig")
        variants = self.usercomponent.features.filter(
            name__in=variants
        )
        if not variants:
            raise Http404()
        try:
            return AssignedContent.objects.from_token(
                token=self.request.auth_token,
                variant=["WebConfig", "TmpConfig"]
            ).content
        except AssignedContent.DoesNotExist:  # pylint: disable=no-member
            if (
                variants.filter(name="TmpConfig") and
                self.request.auth_token.persist < 0
            ):
                ret = AssignedContent.objects.filter(
                    usercomponent=self.usercomponent,
                    attached_to_token__referrer=self.request.auth_token.referrer,  # noqa: E501
                    attached_to_token__persist__lt=0,
                    ctype__name="WebConfig"
                )
                if ret:
                    assert (
                        ret.first().attached_to_token !=
                        self.request.auth_token
                    )
                    ret.update(attached_to_token=self.request.auth_token)
                    return ret.first().content
        ret = self.model.static_create(
            token_size=getattr(settings, "TOKEN_SIZE", 30),
            associated_kwargs={
                "usercomponent": self.usercomponent,
                "ctype": "WebConfig",
                "attached_to_token": self.request.auth_token
            }
        )
        ret.free_data["creation_url"] = self.request.auth_token.referrer.url
        ret.clean()
        ret.save()
        assert(ret.associated.token)
        return ret

    def options(self, request, *args, **kwargs):
        ret = super().options(request, *args, **kwargs)
        self.object = self.get_object()
        ret["Access-Control-Allow-Origin"] = self.object.token.referrer.host
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        b = None
        if self.object.id:
            b = self.object.associated.attachedblobs.filter(
                name="config"
            ).first()
        if not b:
            b = AttachedBlob(
                unique=True, name="config", blob=b"",
                content=self.object.associated
            )
        return self.render_to_response(b.blob)

    def post(self, request, *args, **kwargs):
        if (
            self.request.auth_token.persist < 0 and
            len(self.request.body) > tmpconfig_max
        ):
            return HttpResponse(
                "TmpConfig can only hold: %s bytes" % tmpconfig_max,
                status_code=400
            )
        self.object = self.get_object()
        b = None
        if self.object.id:
            b = self.object.associated.attachedblobs.filter(
                name="config"
            ).first()
        if not b:
            b = AttachedBlob(
                unique=True, name="config", blob=b"",
                content=self.object.associated
            )
        old_size = self.object.get_size()
        oldconfig = b.blob
        b.blob = self.request.body
        self.object.prepared_attachements = {
            "attachedblobs": b
        }

        # a full_clean is here not required
        self.object.clean()

        try:
            self.object.update_used_space(
                self.object.get_size(self.object.prepared_attachements)
                - old_size
            )
        except ValidationError as exc:
            return HttpResponse(
                str(exc), status_code=400
            )
        self.object.save()
        return self.render_to_response(oldconfig)

    def render_to_response(self, config):
        ret = HttpResponse(
            bytes(config), content_type="text/plain"
        )
        ret["X-SPIDER-URL"] = self.request.auth_token.referrer.url
        ret["X-SPIDER-MODIFIED"] = self.object.associated.modified
        ret["X-SPIDER-CREATED"] = self.object.associated.created
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret
