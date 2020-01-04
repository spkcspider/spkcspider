
import logging
from urllib.parse import urljoin

from cryptography import exceptions
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import load_pem_x509_certificate

from django.conf import settings
from django.db import models
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import pgettext
from spkcspider.apps.spider.conf import get_anchor_domain, get_anchor_scheme
from spkcspider.apps.spider import registry
from spkcspider.apps.spider.models import DataContent
from spkcspider.constants import VariantType
from spkcspider.utils.security import get_hashob
from spkcspider.utils.fields import add_by_field

logger = logging.getLogger(__name__)


# Create your models here.

ID_VERIFIERS = {

}


@add_by_field(registry.contents, "_meta.model_name")
class PublicKey(DataContent):
    expose_name = False
    expose_description = True
    appearances = [
        {"name": "PublicKey", "ctype": VariantType.unique}
    ]

    class Meta:
        proxy = True

    @classmethod
    def localize_type_name(cls, name):
        _ = pgettext
        return _("content name", "Public Key")

    def get_info(self):
        ret = super().get_info()
        h = get_hashob()
        if self.prepared_attachements:
            key = self.prepared_attachements["attachedblobs"][0]
        else:
            key = self.associated.attachedblobs.get(name="key")
        h.update(key.blob)
        pubkeyhash = ""
        k = self.get_key_ob(key.blob)
        if k:
            pem = k.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            h2 = get_hashob()
            h2.update(pem)
            pubkeyhash = "pubkeyhash=%s=%s\x1e" % (
                settings.SPIDER_HASH_ALGORITHM.name, h2.finalize().hex()
            )
        return "%shash=%s=%s\x1e%s" % (
            ret, settings.SPIDER_HASH_ALGORITHM.name, h.finalize().hex(),
            pubkeyhash
        )

    def get_key_ob(self, key=None):
        if not key:
            key = self.associated.attachedblobs.get(name="key").blob
        try:
            if b"-----BEGIN CERTIFICATE-----" in key:
                pubkey = load_pem_x509_certificate(
                    key, default_backend()
                ).public_key()
            else:
                pubkey = serialization.load_pem_public_key(
                    key, default_backend()
                )
            return pubkey
        except exceptions.UnsupportedAlgorithm:
            return None
        except ValueError:
            pass

    def get_key_name(self):
        if self.prepared_attachements:
            key = self.prepared_attachements["attachedblobs"][0].as_bytes
        else:
            key = self.associated.attachedblobs.get(name="key").as_bytes
        key = key.decode("ascii")
        # ssh key
        split = key.rsplit(" ", 1)
        if len(split) == 2 and "@" in split[1]:
            return split
        # other key, e.g PEM
        return (key, None)

    def get_content_name(self):
        name = self.get_key_name()[1]
        if not name:
            name = "{}...".format(
                self.associated.getlist("hash", amount=1)[0].split(
                    "=", 1
                )[-1][:20]
            )
        if len(self.associated.description) > 0:
            name = "{}: {}".format(name, self.associated.description[:20])
        return "Key: {}".format(name)

    def get_form(self, scope):
        from .forms import KeyForm
        return KeyForm

    def access_view(self, **kwargs):
        kwargs["object"] = self
        kwargs["key"] = \
            self.associated.attachedblobs.get(
                name="key"
            ).as_bytes.decode("ascii")
        kwargs["hash_algo"] = settings.SPIDER_HASH_ALGORITHM.name
        kwargs["hash"] = self.associated.getlist(
            "hash=%s" % settings.SPIDER_HASH_ALGORITHM.name, 1
        )[0]
        k = self.associated.getlist(
            "pubkeyhash=%s" % settings.SPIDER_HASH_ALGORITHM.name, 1
        )
        if k:
            kwargs["pubkeyhash"] = k[0]
        return render_to_string(
            "spider_keys/key.html", request=kwargs["request"],
            context=kwargs
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


class AnchorMixing(object):
    expose_name = False
    expose_description = True

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
        if not self.associated_id:
            return None
        ret = urljoin(
            "{}://{}".format(
                get_anchor_scheme(), get_anchor_domain()
            ), reverse(
                "spider_keys:anchor-permanent",
                kwargs={"pk": self.associated_id}
            )
        )
        return ret


@add_by_field(registry.contents, "_meta.model_name")
class AnchorServer(AnchorMixing, DataContent):
    """ identify by server """
    appearances = [
        {
            "name": "AnchorServer",
            "ctype": VariantType.anchor,
            "strength": 0
        }
    ]

    class Meta:
        proxy = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Server-based Anchor")

    def get_form(self, scope):
        from .forms import AnchorServerForm
        return AnchorServerForm

    def get_content_name(self):
        return "Anchor: {}".format(self.associated_id)

    def access_anchor(self, **kwargs):
        if self.new_url:
            ret = HttpResponsePermanentRedirect(redirect_to=self.new_url)
        else:
            ret = JsonResponse(self.old_urls)
        ret["Access-Control-Allow-Origin"] = "*"
        return ret


@add_by_field(registry.contents, "_meta.model_name")
class AnchorKey(AnchorMixing, DataContent):
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

    class Meta:
        proxy = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Key-based Anchor")

    def get_content_name(self):
        name = self.associated.attached_to_content.content.get_key_name()[1]
        if not name:
            name = "{}...".format(
                self.associated.attached_to_content.getlist(
                    "hash", amount=1
                )[0].split(
                    "=", 1
                )[-1][:20]
            )
        if len(self.associated.description) > 0:
            name = "{}: {}".format(name, self.associated.description[:20])
        return "AnchorKey: {}".format(name)

    def get_form(self, scope):
        from .forms import AnchorKeyForm
        return AnchorKeyForm

    def access_anchor(self, **kwargs):
        ret = JsonResponse([])
        ret["Access-Control-Allow-Origin"] = "*"
        return ret

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret.setdefault("initial", {})
        ret["request"] = kwargs["request"]
        ret["scope"] = kwargs["scope"]
        return ret

    def get_info(self):
        ret = super().get_info()
        k = self.associated.attached_to_content.getlist(
            "pubkeyhash", amount=1, fullkey=True
        )
        return "%s%s\x1e%s\x1e" % (
            ret,
            self.associated.attached_to_content.getlist(
                "hash", amount=1, fullkey=True
            )[0],
            k[0] if k else ""
        )


# TODO: implement
#
class AnchorLink(AnchorMixing):
    """
        Anchor by Organisation, e.g. government,
        verifier returns token pointing to url
    """

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
