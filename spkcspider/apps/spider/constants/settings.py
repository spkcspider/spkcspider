__all__ = [
    "media_extensions", "image_extensions", "get_anchor_domain",
    "INITIAL_STATIC_TOKEN_SIZE", "STATIC_TOKEN_CHOICES",
    "default_uctoken_duration",
    "force_captcha", "VALID_INTENTIONS", "VALID_SUB_INTENTIONS"
]

import datetime
from django.conf import settings

from django.utils.translation import gettext_lazy as _

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

# if None, set to default Site ID if models are ready
_anchor_domain = getattr(
    settings, "SPIDER_ANCHOR_DOMAIN", None
)


def get_anchor_domain():
    global _anchor_domain
    if _anchor_domain:
        return _anchor_domain
    from django.contrib.sites.models import Site
    _anchor_domain = \
        Site.objects.get(id=settings.SITE_ID).domain
    return _anchor_domain


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

force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))


default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)
