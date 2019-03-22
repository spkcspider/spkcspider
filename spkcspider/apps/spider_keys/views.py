__all__ = ["PermAnchorView"]

from urllib.parse import urljoin

from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic.detail import DetailView

from spkcspider.apps.spider.constants import SPIDER_ANCHOR_DOMAIN

from spkcspider.apps.spider.models import AssignedContent


class PermAnchorView(DetailView):
    queryset = AssignedContent.objects.filter(
        info__contains="\nanchor\n"
    )

    def get(self, request, *args, **kwargs):
        if request.get_host() != SPIDER_ANCHOR_DOMAIN:
            return HttpResponseRedirect(
                location=urljoin(
                    SPIDER_ANCHOR_DOMAIN, request.get_full_path()
                )
            )
        return super().get(request, *args, **kwargs)

    def render_to_response(self, context):
        return HttpResponse("exist")
