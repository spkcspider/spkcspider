__all__ = ("WebConfigForm",)

import logging

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http.response import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView

from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import (
    AuthToken, AssignedContent, ContentVariant
)

from .models import WebConfig
from .forms import WebConfigForm


class WebConfigForm(UCTestMixin, FormView):
    model = WebConfig
    form_class = WebConfigForm

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
        self.request.authtoken = get_object_or_404(
            AuthToken,
            token=token,
            usercomponent__features__name="WebConfig",
        )
        if "referrer" not in self.request.authtoken.extra:
            raise Http404()
        usercomponent = self.request.authtoken.usercomponent
        expire = timezone.now()-usercomponent.token_duration
        if self.request.authtoken.created < expire:
            self.request.authtoken.delete()
            self.request.authtoken = None
            raise Http404()
        return usercomponent

    def get_user(self):
        return self.usercomponent.user

    def get_object(self, queryset=None):
        ret = self.usercomponent.contents.filter(
            info__contains="\ntype=webconfig\nurl={}\n".format(
                self.request.authtoken.extra["referrer"].replace("\n", "%0A")
            ),
            usercomponent=self.usercomponent
        ).first()
        if ret:
            return ret.content
        associated = AssignedContent(
            usercomponent=self.usercomponent,
            ctype=ContentVariant.objects.get(
                name="WebConfig"
            )
        )
        ret = self.model.create_static(associated)
        ret.url = self.request.authtoken.extra["referrer"]
        ret.clean()
        ret.save()
        return ret

    def form_invalid(self, form):
        if settings.DEBUG:
            logging.warning("errors: %s", form.errors)
        return HttpResponse("post to field: \"config\"", status=400)

    def render_to_response(self, context):
        obj = self.get_object()
        field = context["form"].fields["config"]
        raw_value = context["form"].initial.get("config", None)
        value = field.to_python(raw_value)
        ret = HttpResponse(
            value, content_type="text/plain"
        )
        ret["X-SPIDER-URL"] = obj.url
        ret["X-SPIDER-MODIFIED"] = obj.modified
        ret["X-SPIDER-CREATED"] = obj.created
        return ret
