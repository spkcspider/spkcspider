
import logging
from urllib.parse import urljoin

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext
from django.http import HttpResponseRedirect, JsonResponse

from jsonfield import JSONField

from spkcspider.apps.spider.helpers import get_hashob
from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.constants import VariantType
from spkcspider.apps.spider.conf import get_anchor_domain

logger = logging.getLogger(__name__)


# Create your models here.

_htest = get_hashob()
_htest.update(b"test")

_help_text_sig = _("""Signature of Identifier (hexadecimal-encoded)""")

_help_text_key = _(""""Public Key"-Content for signing identifier. It is recommended to use different keys for signing and encryption.""")  # noqa

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
    expose_name = False
    expose_description = True
    appearances = [
        {"name": "PublicKey", "ctype": VariantType.unique.value}
    ]

    key = models.TextField(
        editable=True, validators=[valid_pkey_properties],
        help_text=_(
            "It is recommended to use different keys"
            "for signing and encryption"
        )
    )

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Public Key")

    def get_size(self):
        s = super().get_size()
        s += len(self.key)
        return s

    def get_info(self):
        ret = super().get_info()
        key = self.get_key_name()[0]
        h = get_hashob()
        h.update(key.encode("ascii", "ignore"))
        return "%shash=%s=%s\x1e" % (
            ret, settings.SPIDER_HASH_ALGORITHM.name, h.finalize().hex()
        )

    def get_key_name(self):
        # PEM key
        split = self.key.split("\n")
        if len(split) > 1:
            h = get_hashob()
            h.update(self.key.encode("ascii", "ignore"))
            return (h.finalize().hex(), None)

        # ssh key
        split = self.key.rsplit(" ", 1)
        if len(split) == 2 and "@" in split[1]:
            return split
        # other key
        return (self.key, None)

    def get_content_name(self):
        st = self.get_key_name()
        if st[1]:
            st = st[1]
        else:
            st = "{}...".format(st[0][:10])
        if len(self.associated.description) > 0:
            st = "{}: {}".format(st, self.associated.description[:20])
        return "Key: {}".format(st)

    def get_form(self, scope):
        from .forms import KeyForm
        return KeyForm

    def access_view(self, **kwargs):
        kwargs["object"] = self
        kwargs["algo"] = settings.SPIDER_HASH_ALGORITHM.name
        kwargs["hash"] = self.associated.getlist(
            "hash:%s" % settings.SPIDER_HASH_ALGORITHM.name, 1
        )[0]
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


class AnchorBase(BaseContent):
    expose_name = False
    expose_description = True

    class Meta(BaseContent.Meta):
        abstract = True

    def get_abilities(self, context):
        return {"anchor"}

    def get_priority(self):
        return -10

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret.setdefault("initial", {})
        ret["initial"]["identifier"] = self.get_identifier(kwargs["request"])
        ret["scope"] = kwargs["scope"]
        return ret

    def get_identifier(self, request):
        """ returns id of content, server """
        # security: id can only be faked by own server
        # this should never happen, except with admin access to server
        if not self.associated.id:
            return None
        ret = urljoin(
            "{}://{}".format(request.scheme, get_anchor_domain()), reverse(
                "spider_keys:anchor-permanent",
                kwargs={"pk": self.associated.id}
            )
        )
        return ret


@add_content
class AnchorServer(AnchorBase):
    """ identify by server """
    appearances = [
        {
            "name": "AnchorServer",
            "ctype": VariantType.anchor.value,
            "strength": 0
        }
    ]

    new_url = models.URLField(
        max_length=400, blank=True, null=True,
        help_text=_(
            "Url to new anchor (in case this one is superseded)"
        )
    )
    old_urls = JSONField(
        default=list, blank=True,
        help_text=_(
           "Superseded anchor urls"
        )
    )

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Server-based Anchor")

    def get_size(self):
        s = super().get_size()
        s += 400
        s += len(str(self.old_urls))
        return s

    def get_form(self, scope):
        from .forms import AnchorServerForm
        return AnchorServerForm

    def get_content_name(self):
        return "Anchor: {}".format(self.associated.id)

    def access_anchor(self, **kwargs):
        if self.new_url:
            ret = HttpResponseRedirect(location=self.new_url)
        else:
            ret = JsonResponse(self.old_urls)
        ret["Access-Control-Allow-Origin"] = "*"
        return ret


@add_content
class AnchorKey(AnchorBase):
    """ domain name of pc, signed """
    expose_name = False
    expose_description = True
    appearances = [
        {
            "name": "AnchorKey",
            "ctype": VariantType.anchor+VariantType.unique,
            "strength": 0
        }
    ]

    key = models.OneToOneField(
        PublicKey, on_delete=models.CASCADE, related_name="anchorkey",
        help_text=_help_text_key
    )

    signature = models.CharField(
        max_length=1024, help_text=_help_text_sig, null=False
    )

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Key-based Anchor")

    def get_size(self):
        s = super().get_size()
        s += 1024
        return s

    def get_content_name(self):
        st = self.key.get_key_name()
        if st[1]:
            st = st[1]
        else:
            st = "{}...".format(st[0][:10])
        if len(self.key.associated.description) > 0:
            st = "{}: {}".format(st, self.key.associated.description[:20])
        return st

    def get_form(self, scope):
        from .forms import AnchorKeyForm
        return AnchorKeyForm

    def access_anchor(self, **kwargs):
        ret = JsonResponse([])
        ret["Access-Control-Allow-Origin"] = "*"
        return ret

    def get_info(self):
        ret = super().get_info()
        key = self.key.get_key_name()[0]
        h = get_hashob()
        h.update(key.encode("ascii", "ignore"))
        return "%shash=%s=%s\x1e" % (
            ret, settings.SPIDER_HASH_ALGORITHM.name, h.finalize().hex()
        )


# TODO: implement
# @add_content
class AnchorLink(AnchorBase):
    """
        Anchor by Organisation, e.g. government,
        verifier returns token pointing to url
    """

    class Meta(AnchorBase.Meta):
        abstract = True

    verified_by = models.URLField(max_length=400)

    appearances = [
        {
            "name": "AnchorLink",
            "ctype": VariantType.anchor + VariantType.unique,
            "strength": 10
        }
    ]

    def access_anchor(self, **kwargs):
        ret = JsonResponse(self.verified_by)
        ret["Access-Control-Allow-Origin"] = "*"
        return ret

    def get_form(self, scope):
        raise NotImplementedError

    def get_info(self):
        return "{}verified_by={}\x1e".format(
            super().get_info(unique=True, unlisted=False),
            self.verified_by
        )
