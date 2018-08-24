from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext


import hashlib
import logging

from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.constants import UserContentType

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.KEY_HASH_ALGO)
_htest.update(b"test")


ID_VARIANTS = [
    ("", "")
]

ID_VERIFIERS = {

}


def valid_pkey_properties(key):
    if "PRIVAT" in key.upper():
        raise ValidationError(_('Private Key'))
    if key.strip() != key:
        raise ValidationError(_('Not trimmed'))
    if len(key) < 100:
        raise ValidationError(_('Not a key'))


@add_content
class PublicKey(BaseContent):
    appearances = [(
        "PublicKey",
        UserContentType.public+UserContentType.unique
    )]

    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    note = models.TextField(max_length=100, default="", null=False, blank=True)

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", "Public Key")

    def get_info(self):
        ret = super().get_info()
        key = self.get_key_name()[0]
        h = hashlib.new(settings.KEY_HASH_ALGO)
        h.update(key.encode("ascii", "ignore"))
        return "%shash:%s=%s\n" % (
            ret, settings.KEY_HASH_ALGO, h.hexdigest()
        )

    def get_key_name(self):
        # PEM key
        split = self.key.split("\n")
        if len(split) > 1:
            return (self.key, None)

        # ssh key
        split = self.key.rsplit(" ", 1)
        if len(split) == 2 and "@" in split[1]:
            return split
        # other key
        return (self.key, None)

    def __str__(self):
        if not self.id:
            return gettext("Public Key")
        st = self.get_key_name()
        if st[1]:
            st = st[1]
        else:
            st = "{}...".format(st[0][:10])
        if len(self.note) > 0:
            st = "{}: {}".format(st, self.note[:20])
        return st

    def get_form(self, scope):
        from .forms import KeyForm
        return KeyForm

    def render_view(self, **kwargs):
        kwargs["object"] = self
        kwargs["algo"] = settings.KEY_HASH_ALGO
        kwargs["hash"] = self.associated.getlist(
            "hash:%s" % settings.KEY_HASH_ALGO
        )[0]
        return render_to_string(
            "spider_keys/key.html", request=kwargs["request"],
            context=kwargs
        )


###############################
# not implemented yet, stubs, needs Design, forms and rendering
# anchors are designed to be unique usernames.
# the returned url should be used for authentication/validation of user
#    needs design

# @add_content
class AnchorServer(object):  # BaseContent):
    """ identify by server """
    appearances = [(
        "AnchorServer",
        UserContentType.link_private+UserContentType.anchor
    )]

    def get_form(self):
        from .forms import AnchorServerForm
        return AnchorServerForm

    def get_identifier(self, request):
        """ returns id of content, server """
        # security: can only be faked by own server
        # so that's no risk
        return "{}@{}".format(
            getattr(self.associated, "id", None),
            getattr(settings, "ANCHOR_HOST", request.get_host())
        )


# @add_content
class AnchorKey(AnchorServer):
    """ domain name of pc, signed """
    key = models.ForeignKey(
        PublicKey, on_delete=models.CASCADE, related_name="+"
    )

    signature = models.CharField(max_length=1024)

    appearances = [(
        "AnchorKey",
        UserContentType.unique+UserContentType.link_private +
        UserContentType.anchor
    )]

    def generate_raw(self, **kwargs):
        # anchors must be generated on client
        # anchor_format = key_<hash of key>
        return {
            "type": "key",
            "identifier": self.get_identifier(kwargs["request"]),
            "signature": self.signature,
            "key": self.key.get_key_name()[0]
        }


# @add_content
class AnchorGov(object):
    """
        Anchor by Organisation, e.g. government,
        verifier returns token pointing to url
    """
    idtype = models.CharField(max_length=10, null=False, choices=ID_VARIANTS)
    token = models.CharField(max_length=100, null=False)

    appearances = [(
        "AnchorGov",
        UserContentType.unique+UserContentType.link_private +
        UserContentType.anchor
    )]
