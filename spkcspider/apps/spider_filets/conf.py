__all__ = (
    "DEFAULT_LICENSE_FILE", "DEFAULT_LICENSE_TEXT", "LICENSE_CHOICES"
)

from django.conf import settings

LICENSE_CHOICES = getattr(
    settings, "SPIDER_LICENSE_CHOICES", {}
)
DEFAULT_LICENSE_FILE = getattr(
    settings, "SPIDER_DEFAULT_LICENSE_FILE",
    lambda uc, user: "other"
)
if not callable(DEFAULT_LICENSE_FILE):
    _DEFAULT_LICENSE_FILE = DEFAULT_LICENSE_FILE

    def DEFAULT_LICENSE_FILE(uc, user):
        return _DEFAULT_LICENSE_FILE

DEFAULT_LICENSE_TEXT = getattr(
    settings, "SPIDER_DEFAULT_LICENSE_TEXT", DEFAULT_LICENSE_FILE
)

if not callable(DEFAULT_LICENSE_TEXT):
    _DEFAULT_LICENSE_TEXT = DEFAULT_LICENSE_TEXT

    def DEFAULT_LICENSE_TEXT(uc, user):
        return _DEFAULT_LICENSE_TEXT
