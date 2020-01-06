__all__ = [
    "rate_limit_default", "allow_all_filter",
    "embed_file_default", "has_admin_permission",
    "LimitedTemporaryFileUploadHandler", "validate_url_default",
    "get_quota", "clean_verifier",
    "clean_verifier_url", "clean_spider_inline"
]

import base64
import logging
import math
import os
import random
import time
from urllib.parse import urlsplit

import requests
from rdflib import XSD, Literal

import ratelimit
from django.conf import settings
from django.core.files.uploadhandler import (
    StopFutureHandlers, StopUpload, TemporaryFileUploadHandler
)
from django.http import Http404
from django.http.request import validate_host
from django.shortcuts import redirect
from django.test import Client
from django.urls import reverse
from django.views.decorators.cache import never_cache
from spkcspider.constants import spkcgraph

from .conf import get_anchor_domain, get_anchor_scheme, get_requests_params
from .signals import failed_guess

# seed with real random
_nonexhaustRandom = random.Random(os.urandom(30))


def rate_limit_default(request, view):
    group = getattr(view, "rate_limit_group", None)
    if group:
        ratelimit.get_ratelimit(
            request=request, group=group, key="user_or_ip",
            inc=True, rate=(math.inf, 3600)
        )
    results = failed_guess.send_robust(sender=view, request=request)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.error(
                "%s failed", receiver, exc_info=result
            )
    # with 0.4% chance reseed
    if _nonexhaustRandom.randint(0, 249) == 0:
        _nonexhaustRandom.seed(os.urandom(10))
    time.sleep(_nonexhaustRandom.random()/2)
    raise Http404()


def allow_all_filter(*args, **kwargs):
    return True


def get_quota(user, quota_type):
    return getattr(user, "quota_{}".format(quota_type), None)


def clean_verifier_url(url):
    if "://" not in url:
        return False
    return True


_default_allowed_hosts = ['localhost', '127.0.0.1', '[::1]']


def clean_spider_inline(url):
    allowed_hosts = settings.ALLOWED_HOSTS
    if settings.DEBUG and not allowed_hosts:
        allowed_hosts = _default_allowed_hosts
    if validate_host(url, allowed_hosts):
        inline_domain = urlsplit(url)
        return inline_domain.netloc or inline_domain.path.split("/", 1)[0]
    return None


def clean_verifier(request, view):
    if not request.auth_token or not request.auth_token.referrer:
        return False
    url = request.auth_token.referrer.url
    if request.method == "POST":
        url = request.POST.get("url", "")
        if not url.startswith(request.auth_token.referrer.url):
            return False
    if "://" not in url:
        return False
    if request.method == "GET":
        # don't spam verifier
        return True
    params, inline_domain = get_requests_params(url)
    if inline_domain:
        response = Client().head(
            url, follow=True, secure=True, Connection="close",
            SERVER_NAME=inline_domain
        )
        if response.status_code >= 400:
            return False
    else:
        try:
            with requests.head(
                url, stream=True, **params,
                headers={"Connection": "close"}
            ) as resp:
                resp.close()
                resp.raise_for_status()
        except Exception:
            return False
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
                settings, "SPIDER_MAX_FILE_SIZE_STAFF", None
            )
        else:
            max_length = getattr(
                settings, "SPIDER_MAX_FILE_SIZE", None
            )
        if not max_length:
            return True

        # superuser can upload as much as he wants
        if self.request.user.is_superuser:
            return True

        return content_length <= max_length


def validate_url_default(url, view=None):
    url = urlsplit(url)
    if url.scheme == "https":
        return True
    elif url.scheme == "http":
        # MAKE SURE that you control your dns
        if url.netloc.endswith(".onion"):
            return True
        elif (
            get_anchor_domain() == url.netloc and
            get_anchor_scheme() == "http"
        ):
            return True
        elif settings.DEBUG:
            return True
    return False


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
        getattr(settings, "FILE_DIRECT_DOWNLOAD", False)
    ):
        # link always direct to files in exports
        url = value.url
        if "://" not in getattr(settings, "MEDIA_URL", ""):
            url = "{}{}".format(context["hostpart"], url)
        return Literal(
            url,
            datatype=spkcgraph["hashableURI"],
        )
    else:
        # only file filet has files yet
        url = content.associated.get_absolute_url("download")
        url = "{}{}?{}".format(
            context["hostpart"],
            url, context["context"]["sanitized_GET"]
        )
        return Literal(
            url,
            datatype=spkcgraph["hashableURI"],
        )


def has_admin_permission(obj, request):
    # allow only non travel protected user with superuser and staff permissions
    if not request.user.is_active or not request.user.is_staff:
        return False
    # user is authenticate now
    assert request.user.is_authenticated
    if not request.session["is_travel_protected"]:
        from .models import AssignedContent
        t = AssignedContent.travel.get_active_for_request(
            request
        ).exists()
        # auto activates on trying to access admin but not deactivate
        if t:
            request.session["is_travel_protected"] = t
    if request.session["is_travel_protected"]:
        return False
    return True


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
