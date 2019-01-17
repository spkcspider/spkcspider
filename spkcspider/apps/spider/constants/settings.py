__all__ = [
    "INITIAL_NONCE_SIZE", "NONCE_CHOICES", "default_uctoken_duration",
    "force_captcha", "VALID_INTENTIONS", "VALID_SUB_INTENTIONS"
]

import datetime
from django.conf import settings

from django.utils.translation import gettext_lazy as _


INITIAL_NONCE_SIZE = str(getattr(settings, "INITIAL_NONCE_SIZE", 12))

NONCE_CHOICES = [
    ("", ""),
    (INITIAL_NONCE_SIZE, _("default ({} Bytes)")),
    ("3", _("low ({} Bytes)")),
    ("12", _("medium ({} Bytes)")),
    ("30", _("high ({} Bytes)")),
]

VALID_INTENTIONS = set(getattr(
    settings, "SPIDER_VALID_INTENTIONS",
    ["auth", "login", "persist", "payment", "sl", "live"]
))
VALID_SUB_INTENTIONS = set(["sl", "live"])

force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))


default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)
