

import hashlib
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rdflib.namespace import Namespace


namespace_verifier = Namespace("https://spkcspider.net/schemes/verifier/")

VERIFICATION_CHOICES = [
    ("pending", _("pending")),
    ("verified", _("verified")),
    ("rejected", _("rejected")),
]


def get_hashob():
    return hashlib.new(getattr(settings, "VERIFICATION_HASH_ALGO", "sha512"))


BUFFER_SIZE = 65536  # read in 64kb chunks
