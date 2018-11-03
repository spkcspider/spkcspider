__all__ = [
    "rate_limit_default", "allow_all_filter",
    "embed_file_default", "has_admin_permission",
    "LimitedTemporaryFileUploadHandler"
]

import time
import base64
import logging
from django.core.files.uploadhandler import (
    TemporaryFileUploadHandler, StopUpload, StopFutureHandlers
)
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.conf import settings
from .signals import failed_guess
from rdflib import Literal, XSD


def rate_limit_default(view, request):
    results = failed_guess.send_robust(view=view, request=request)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.exception(result)
    time.sleep(1)
    raise Http404()


def allow_all_filter(*args, **kwargs):
    return True


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
        self.activated = self.check_allowed_size(content_length)

    def new_file(self, *args, **kwargs):
        if not self.activated:
            raise StopFutureHandlers()
        return super().new_file(*args, **kwargs)

    def receive_data_chunk(self, raw_data, start):
        if not self.activated:
            raise StopUpload(True)
        return super().receive_data_chunk(raw_data, start)

    def file_complete(self, file_size):
        """Return a file object if this handler is activated."""
        if not self.activated:
            return
        return super().file_complete(file_size)

    def check_allowed_size(self, content_length):
        if self.request.user.is_staff:
            max_length = getattr(
                settings, "MAX_FILE_SIZE_STAFF", None
            )
        else:
            max_length = getattr(
                settings, "MAX_FILE_SIZE", None
            )
        if not max_length:
            return True

        # admin can upload as much as he wants
        if self.request.user.is_superuser:
            return True

        return content_length <= max_length


def embed_file_default(name, value, content, context):

    override = (
        (
            context["request"].user.is_superuser or
            context["request"].user.is_staff
        ) and context["request"].GET.get("embed_big", "") == "true"
    )
    if (
        value.size < getattr(settings, "MAX_EMBED_SIZE", 4000000) or
        override
    ):
        return Literal(
            base64.b64encode(value.read()),
            datatype=XSD.base64Binary,
            normalize=False
        )
    elif (
        context["scope"] == "export" or
        getattr(settings, "DIRECT_FILE_DOWNLOAD", False)
    ):
        # link always direct to files in exports
        url = value.url
        if "://" not in getattr(settings, "MEDIA_URL", ""):
            url = "{}{}".format(context["hostpart"], url)
        return Literal(
            url,
            datatype=XSD.anyURI,
        )
    else:
        # only file filet has files yet
        url = content.associated.get_absolute_url("download")
        url = "{}{}?{}".format(
            context["hostpart"],
            url, context["context"]["spider_GET"].urlencode()
        )
        return Literal(
            url,
            datatype=XSD.anyURI,
        )


def has_admin_permission(self, request):
    # allow only non faked user with superuser and staff permissions
    if request.session.get("is_fake", False):
        return False
    return request.user.is_active and request.user.is_staff


@never_cache
def admin_login(self, request, extra_context=None):
    """
    Display the login form for the given HttpRequest.
    """
    if request.method == 'GET' and self.has_permission(request):
        # Already logged-in, redirect to admin index
        index_path = reverse('admin:index', current_app=self.name)
        return redirect(index_path)
    else:
        loginpath = getattr(
            settings,
            "LOGIN_URL",
            reverse("auth:login")
        )
        return redirect(loginpath)
