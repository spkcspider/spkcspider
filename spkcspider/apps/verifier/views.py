
from django.http import JsonResponse
from django.views.generic.edit import CreateView, DetailsView

from .models import DataVerificationTag
from .forms import CreateEntryForm


class CreateEntry(CreateView):
    model = DataVerificationTag
    form_class = CreateEntryForm


class VerifyEntry(DetailsView):
    model = DataVerificationTag
    slug_field = "hash"
    slug_url_kwarg = "hash"

    def render_to_response(self, context):
        ret = {
            "verified": "unverified"
        }
        if self.object.verification_state == "verified":
            ret["verified"] = self.object.checked.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )
        if self.object.source_type == "url":
            ret["source"] = self.object.source
        return JsonResponse(ret)
