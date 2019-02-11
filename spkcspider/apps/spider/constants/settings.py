__all__ = [
    "INITIAL_STATIC_TOKEN_SIZE", "STATIC_TOKEN_CHOICES",
    "default_uctoken_duration",
    "force_captcha", "VALID_INTENTIONS", "VALID_SUB_INTENTIONS"
]

import datetime
from django.conf import settings

from django.utils.translation import gettext_lazy as _


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
    ["auth", "domain", "live", "login", "persist", "payment", "sl"]
))
VALID_SUB_INTENTIONS = set(["sl", "live"])

force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))


default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)
