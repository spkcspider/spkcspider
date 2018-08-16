from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext
from django.http import HttpResponse


import hashlib
import logging

from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.constants import UserContentType

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.KEY_HASH_ALGO)
_htest.update(b"test")


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
        UserContentType.public.value+UserContentType.unique.value
    )]

    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    note = models.TextField(max_length=100, default="", null=False, blank=True)

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", "Public Key")

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        key = self.get_key_name()[0]
        h = hashlib.new(settings.KEY_HASH_ALGO)
        h.update(key.encode("ascii", "ignore"))
        return "%shash:%s=%s;" % (
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

    def render(self, **kwargs):
        from .forms import KeyForm
        if kwargs["scope"] == "key" or kwargs["raw"]:
            return HttpResponse(self.key, content_type="text/plain")
        elif kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Public Key")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Public Key")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = KeyForm(
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = KeyForm(
                    instance=kwargs["form"].save()
                )
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            kwargs["object"] = self
            kwargs["algo"] = settings.KEY_HASH_ALGO
            kwargs["hash"] = self.associated.get_value(
                "hash:%s" % settings.KEY_HASH_ALGO
            )
            return render_to_string(
                "spider_keys/key.html", request=kwargs["request"],
                context=kwargs
            )

    def save(self, *args, **kwargs):
        key = self.get_key_name()[0]
        if self._former_key != key:
            h = hashlib.new(settings.KEY_HASH_ALGO)
            h.update(key.encode("ascii", "ignore"))
            self.hash = h.hexdigest()
        super().save(*args, **kwargs)
