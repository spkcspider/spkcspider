# NOT IMPORTED BY DEFAULT
# especially because of gettext_lazy import

__all__ = [
    "VERIFICATION_CHOICES"
]

from django.utils.translation import gettext_lazy as _


VERIFICATION_CHOICES = [
    ("pending", _("pending")),
    ("verified", _("verified")),
    ("invalid", _("invalid")),
    ("rejected", _("rejected")),
]
