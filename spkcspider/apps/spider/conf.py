__all__ = [
    "media_extensions", "image_extensions",
    "get_anchor_domain", "get_anchor_scheme",
    "INITIAL_STATIC_TOKEN_SIZE", "STATIC_TOKEN_CHOICES",
    "default_uctoken_duration", "TOKEN_SIZE", "FILE_TOKEN_SIZE",
    "force_captcha", "VALID_INTENTIONS", "VALID_SUB_INTENTIONS",
    "get_requests_params"
]
import datetime
import functools
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import resolve_url
from django.urls import NoReverseMatch
from django.utils.translation import gettext_lazy as _
from spkcspider.constants import host_tld_matcher
from spkcspider.utils.settings import get_settings_func

# webbrowser supported image formats
image_extensions = set(getattr(
    settings, "SPIDER_IMAGE_EXTENSIONS", {
        "jpg", "jpeg", "bmp", "png", "ico", "svg", "gif", "webp"
    }
))

media_extensions = set(getattr(
    settings, "SPIDER_MEDIA_EXTENSIONS", {
        "mp4", "ogg", "flac", "mp3", "webm", "wav", "avi"
    }
))


@functools.lru_cache(1)
def get_anchor_domain():
    # if None, set to default Site ID if models are ready
    _anchor_domain = getattr(
        settings, "SPIDER_ANCHOR_DOMAIN", None
    )
    if _anchor_domain:
        try:
            return resolve_url(_anchor_domain)
        except NoReverseMatch:
            return _anchor_domain
    from django.contrib.sites.models import Site
    return Site.objects.get(id=settings.SITE_ID).domain


@functools.lru_cache(1)
def get_anchor_scheme():
    if getattr(settings, "SPIDER_ANCHOR_SCHEME", None) is not None:
        return settings.SPIDER_ANCHOR_SCHEME
    _anchor_domain = get_anchor_domain()
    if any(
        re.search(pattern, _anchor_domain)
        for pattern in getattr(settings, "SECURE_REDIRECT_EXEMPT", [])
    ):
        return "http"
    return "https"


INITIAL_STATIC_TOKEN_SIZE = str(
    getattr(settings, "SPIDER_INITIAL_STATIC_TOKEN_SIZE", 12)
)

STATIC_TOKEN_CHOICES = [
    ("", ""),
    (INITIAL_STATIC_TOKEN_SIZE, _("default ({} Bytes)")),
    ("3", _("low ({} Bytes)")),
    ("12", _("medium ({} Bytes)")),
    ("30", _("high ({} Bytes)")),
]

VALID_INTENTIONS = set(getattr(
    settings, "SPIDER_VALID_INTENTIONS",
    {"auth", "domain", "live", "login", "payment", "persist", "sl"}
))
VALID_SUB_INTENTIONS = {"sl", "live"}

TOKEN_SIZE = getattr(settings, "TOKEN_SIZE", 30)
FILE_TOKEN_SIZE = getattr(settings, "FILE_TOKEN_SIZE", TOKEN_SIZE)

force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))


default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)


def get_requests_params(url):
    """
        returns (request parameters, inline url or None)
    """
    _url = host_tld_matcher.match(url)
    if not _url:
        raise ValidationError(
            _("Invalid URL: \"%(url)s\""),
            code="invalid_url",
            params={"url": url}
        )
    _url = _url.groupdict()
    mapper = settings.SPIDER_REQUEST_KWARGS_MAP
    return (
        mapper.get(
            _url["host"],
            mapper.get(
                _url["tld"],  # maybe None but then fall to retrieval 3
                mapper[b"default"]
            )
        ),
        get_settings_func(
            "SPIDER_INLINE",
            "spkcspider.apps.spider.functions.clean_spider_inline",
            exclude=frozenset({True})
        )(_url["host"])
    )
