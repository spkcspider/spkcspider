__all__ = ("PushTagView",)

from django.conf import settings
from django.http import Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http.response import JsonResponse

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView
from django.shortcuts import redirect

from spkcspider.apps.spider.views import UCTestMixin
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import (
    AuthToken, AssignedContent, UserComponent
)
from .models import SpiderTag, TagLayout
from .forms import SpiderTagForm


class PushTagView(UCTestMixin, FormView):
    model = SpiderTag
    form_class = SpiderTagForm
    variant = None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
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

    def get(self, request, *args, **kwargs):
        index = UserComponent.objects.get(
            user=self.usercomponent.user,
            name="index"
        )
        layouts = TagLayout.objects.filter(
            Q(usertag__isnull=True) |
            Q(usertag__associated_rel__usercomponent=index)
        ).values_list("name", flat=True)
        ret = JsonResponse(
            {"layout": list(layouts)}
        )
        # allow cors requests for accessing data
        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret

    def post(self, request, *args, **kwargs):
        associated = AssignedContent(
            usercomponent=self.usercomponent,
            ctype=self.variant,
        )
        associated.token_generate_new_size = \
            getattr(settings, "TOKEN_SIZE", 30)
        self.object = self.model.static_create(associated=associated)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.clean()
        self.object.save()
        form.save_m2m()
        assert(self.object.associated.token)
        ret = redirect(
            "spider_base:ucontent-access",
            token=self.object.associated.token,
            access="push_update"
        )

        ret["Access-Control-Allow-Origin"] = \
            self.request.auth_token.referrer.host
        return ret
