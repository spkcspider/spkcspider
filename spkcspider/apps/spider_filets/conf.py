__all__ = (
    "DEFAULT_LICENSE_FILE", "LICENSE_CHOICES_FILE",
    "DEFAULT_LICENSE_TEXT", "LICENSE_CHOICES_TEXT"
)

from django.conf import settings
from django.utils.translation import gettext_lazy as _

LICENSE_CHOICES_FILE = getattr(
    settings, "SPIDER_LICENSE_CHOICES_FILE", {
        "other": (_("Other"), "")
    }
)
DEFAULT_LICENSE_FILE = getattr(
    settings, "SPIDER_DEFAULT_LICENSE_FILE", "other"
)

LICENSE_CHOICES_TEXT = getattr(
    settings, "SPIDER_LICENSE_CHOICES_TEXT", {
        "other": (_("Other"), "")
    }
)

DEFAULT_LICENSE_TEXT = getattr(
    settings, "DEFAULT_LICENSE_TEXT", "other"
)
