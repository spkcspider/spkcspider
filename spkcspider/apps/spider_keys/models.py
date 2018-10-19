
import logging
import hashlib

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext


from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.constants import UserContentType

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.SPIDER_HASH_ALGORITHM)
_htest.update(b"test")

_help_text_sig = _(""" Signed identifier """)

_help_text_key = _(""" Public Key-Content """)

ID_VERIFIERS = {

}


def valid_pkey_properties(key):
    _ = gettext
    if "PRIVAT" in key.upper():
        raise ValidationError(_('Private Key'))
    if key.strip() != key:
        raise ValidationError(_('Not trimmed'))
    if len(key) < 100:
        raise ValidationError(_('Not a key'))


@add_content
class PublicKey(BaseContent):
    appearances = [
        {"name": "PublicKey", "ctype": UserContentType.unique.value}
    ]

    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    note = models.TextField(max_length=100, default="", null=False, blank=True)

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", "Public Key")

    def get_info(self):
        ret = super().get_info()
        key = self.get_key_name()[0]
        h = hashlib.new(settings.SPIDER_HASH_ALGORITHM)
        h.update(key.encode("ascii", "ignore"))
        return "%shash:%s=%s\n" % (
            ret, settings.SPIDER_HASH_ALGORITHM, h.hexdigest()
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
            return super().__str__()
        st = self.get_key_name()
        if st[1]:
            st = st[1]
        else:
            st = "{}...".format(st[0][:10])
        if len(self.note) > 0:
            st = "{}: {}".format(st, self.note[:20])
        return "Key: {}".format(st)

    def get_form(self, scope):
        from .forms import KeyForm
        return KeyForm

    def render_view(self, **kwargs):
        if "raw" in kwargs["request"].GET:
            k = kwargs.copy()
            k["scope"] = "raw"
            return self.render_serialize(**k)
        kwargs["object"] = self
        kwargs["algo"] = settings.SPIDER_HASH_ALGORITHM
        kwargs["hash"] = self.associated.getlist(
            "hash:%s" % settings.SPIDER_HASH_ALGORITHM, 1
        )[0].split("=", 1)[1]
        return (
            render_to_string(
                "spider_keys/key.html", request=kwargs["request"],
                context=kwargs
            ),
            ""
        )

# Anchors can ONLY be used for server content.
# Clients have to be verified seperately
# 1 To verify client use this trick:
# requesting party redirects user to server, with a return address in GET
# the server generates a secret
# the user authenticates and redirects to the url plus hash of secret
# the server sends secret via post to requesting party
# the requesting party can verify that both: client and server are connected
# this means: anchors are valid for this client
# or 2: generate a token
# or 3: use oauth

# advantage of 1,2: simple
# implementation: if requester in GET, create token and
# redirect after auth to requester with hash of token
# post token to requester

# TODO: make hash algorithm configurable


@add_content
class AnchorServer(BaseContent):
    """ identify by server """
    appearances = [
        {
            "name": "AnchorServer",
            "ctype": UserContentType.anchor.value,
            "strength": 7
        }
    ]

    def get_form(self, scope):
        from .forms import AnchorServerForm
        return AnchorServerForm

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret.setdefault("initial", {})
        ret["initial"]["identifier"] = self.get_identifier(
            kwargs["request"]
        )
        ret["scope"] = kwargs["scope"]
        return ret

    def get_identifier(self, request):
        """ returns id of content, server """
        # security: id can only be faked by own server
        # this should never happen, except with access to server
        return "{}@{}".format(
            getattr(self.associated, "id", None),
            request.get_host()
        )


@add_content
class AnchorKey(AnchorServer):
    """ domain name of pc, signed """
    key = models.ForeignKey(
        PublicKey, on_delete=models.CASCADE, related_name="+",
        help_text=_help_text_key
    )

    signature = models.CharField(max_length=1024, help_text=_help_text_sig)

    appearances = [
        {
            "name": "AnchorKey",
            "ctype": UserContentType.anchor+UserContentType.unique,
            "strength": 7
        }
    ]

    def get_form(self, scope):
        from .forms import AnchorKeyForm
        return AnchorKeyForm


# TODO: implement
# @add_content
class AnchorGov(object):
    """
        Anchor by Organisation, e.g. government,
        verifier returns token pointing to url
    """
    url = models.URLField()
    token = models.CharField(max_length=100, null=False)

    appearances = [
        {
            "name": "AnchorGov",
            "ctype": UserContentType.anchor+UserContentType.unique,
            "strength": 7
        }
    ]

    def get_form(self, scope):
        raise NotImplementedError

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret.setdefault("initial", {})
        ret["initial"]["identifier"] = self.get_identifier(
            kwargs["request"]
        )
        ret["scope"] = kwargs["scope"]
        return ret
