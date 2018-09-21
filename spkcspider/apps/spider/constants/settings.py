__all__ = [
    "INITIAL_NONCE_SIZE", "NONCE_CHOICES", "default_uctoken_duration",
    "protected_names", "force_captcha"
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


force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))

protected_names = ["index", "fake_index"]


default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)
