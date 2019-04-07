__all__ = ["PermAnchorView"]

from urllib.parse import urljoin

from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic.detail import DetailView

from spkcspider.apps.spider.conf import get_anchor_domain

from spkcspider.apps.spider.models import AssignedContent


class PermAnchorView(DetailView):
    queryset = AssignedContent.objects.filter(
        info__contains="\x1eanchor\x1e"
    )

    def get(self, request, *args, **kwargs):
        if request.get_host() != get_anchor_domain():
            return HttpResponseRedirect(
                location=urljoin(
                    get_anchor_domain(), request.get_full_path()
                )
            )
        return super().get(request, *args, **kwargs)

    def render_to_response(self, context):
        return HttpResponse("exist")
