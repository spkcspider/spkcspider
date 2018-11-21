

import hashlib
from django.conf import settings
from django.utils.translation import gettext_lazy as _


VERIFICATION_CHOICES = [
    ("pending", _("pending")),
    ("verified", _("verified")),
    ("rejected", _("rejected")),
]


def get_hashob():
    return hashlib.new(getattr(settings, "VERIFICATION_HASH_ALGO", "sha512"))


BUFFER_SIZE = 65536  # read in 64kb chunks
