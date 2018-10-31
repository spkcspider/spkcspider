
from django.views.generic.edit import CreateView
from django.views.generic.detail import DetailView
from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect

from .models import DataVerificationTag
from .forms import CreateEntryForm
from .constants import namespace_verifier


class CreateEntry(CreateView):
    model = DataVerificationTag
    form_class = CreateEntryForm
    template_name = "spider_verifier/dv_form.html"

    def get_context_data(self, **kwargs):
        kwargs["legend"] = _("Send spider or content to verify")
        kwargs["confirm"] = _("Send")
        return super().get_context_data(**kwargs)

    def form_invalid(self, form):
        print(form.errors, form.fields["hash"].initial)
        q = DataVerificationTag.objects.filter(
            hash=form.fields["hash"].initial
        ).first()
        if q:
            return HttpResponseRedirect(q.get_absolute_url())
        return super().form_invalid(form)


class VerifyEntry(DetailView):
    model = DataVerificationTag
    slug_field = "hash"
    slug_url_kwarg = "hash"
    template_name = "spider_verifier/dv_detail.html"

    def get_context_data(self, **kwargs):
        kwargs["namespace"] = namespace_verifier
        return super().get_context_data(**kwargs)

    # "%a, %d %b %Y %H:%M:%S %z"
