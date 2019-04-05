__all__ = (
    "DEFAULT_LICENSE_FILE", "LICENSE_CHOICES_FILE",
    "DEFAULT_LICENSE_TEXT", "LICENSE_CHOICES_TEXT"
)

from django.conf import settings
from django.utils.translation import gettext_lazy as _

LICENSE_CHOICES_FILE = getattr(
    settings, "SPIDER_LICENSE_CHOICES_FILE", {
        "other": (_("Other"), ""),
        "pd": (_("Public Domain"), _("Public Domain"))
    }
)
DEFAULT_LICENSE_FILE = getattr(
    settings, "SPIDER_DEFAULT_LICENSE_FILE",
    lambda uc, user: "pd"
)
if not callable(DEFAULT_LICENSE_FILE):
    _DEFAULT_LICENSE_FILE = DEFAULT_LICENSE_FILE

    def DEFAULT_LICENSE_FILE(uc, user):
        return _DEFAULT_LICENSE_FILE

LICENSE_CHOICES_TEXT = getattr(
    settings, "SPIDER_LICENSE_CHOICES_TEXT", {
        "other": (_("Other"), ""),
        "pd": (_("Public Domain"), _("Public Domain"))
    }
)

DEFAULT_LICENSE_TEXT = getattr(
    settings, "DEFAULT_LICENSE_TEXT",
    lambda uc, user: "pd"
)

if not callable(DEFAULT_LICENSE_TEXT):
    _DEFAULT_LICENSE_TEXT = DEFAULT_LICENSE_TEXT

    def DEFAULT_LICENSE_TEXT(uc, user):
        return _DEFAULT_LICENSE_TEXT
