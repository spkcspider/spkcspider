__all__ = ["HashAlgoView", "CreateEntry", "HashAlgoView"]


from django.views.generic.edit import CreateView
from django.views.generic.detail import DetailView
from django.views import View
from django.http import HttpResponseRedirect, HttpResponse
from django.core.files.uploadhandler import (
    TemporaryFileUploadHandler, StopUpload, StopFutureHandlers
)
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.conf import settings
from rdflib import Literal

from .models import DataVerificationTag
from .forms import CreateEntryForm
from .constants import namespace_verifier


class LimitedTemporaryFileUploadHandler(TemporaryFileUploadHandler):
    activated = False

    def handle_raw_input(
        self, input_data, META, content_length, boundary, encoding=None
    ):
        """
        Use the content_length to signal whether or not this handler should be
        used.
        """
        # disable upload if too big
        self.activated = content_length <= settings.VERIFIER_MAX_SIZE_ACCEPTED

    def new_file(self, *args, **kwargs):
        if not self.activated:
            raise StopFutureHandlers()
        return super().new_file(self, *args, **kwargs)

    def receive_data_chunk(self, raw_data, start):
        if not self.activated:
            raise StopUpload(True)
        return super().receive_data_chunk(raw_data, start)

    def file_complete(self, file_size):
        """Return a file object if this handler is activated."""
        if not self.activated:
            return
        return super().file_complete(file_size)


class CreateEntry(CreateView):
    model = DataVerificationTag
    form_class = CreateEntryForm
    template_name = "spider_verifier/dv_form.html"
    upload_handlers = [
        LimitedTemporaryFileUploadHandler
    ]

    _dispatch = method_decorator(csrf_protect)(CreateView.dispatch)

    def dispatch(self, request, *args, **kwargs):
        if self.upload_handlers:
            request.upload_handlers = [
                i(request) for i in self.upload_handlers
            ]
        return self._dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        if "initial" not in ret:
            # {} not hashable
            ret["initial"] = {}
        ret["initial"]["url"] = self.request.META.get("Referer", "")
        return ret

    def form_invalid(self, form):
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
        kwargs["verified"] = Literal(self.object.checked)
        return super().get_context_data(**kwargs)


class HashAlgoView(View):

    def get(self, request, *args, **kwargs):
        algo = getattr(
            settings, "VERIFICATION_HASH_ALGO", "sha512"
        )
        return HttpResponse(
            content=algo.encode("utf8"),
            content_type="text/plain"
        )
