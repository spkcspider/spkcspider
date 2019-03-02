__all__ = [
    "VERIFICATION_CHOICES", "BUFFER_SIZE"
]


from django.utils.translation import gettext_lazy as _


VERIFICATION_CHOICES = [
    ("pending", _("pending")),
    ("verified", _("verified")),
    ("invalid", _("invalid")),
    ("rejected", _("rejected")),
]


BUFFER_SIZE = 65536  # read in 64kb chunks
