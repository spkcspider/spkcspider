from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext


import hashlib
import logging

from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.KEY_HASH_ALGO)
_htest.update(b"test")

if settings.MAX_HASH_SIZE > len(_htest.hexdigest()):
    raise Exception("MAX_HASH_SIZE too small to hold digest in hexadecimal")


def valid_pkey_properties(key):
    if "PRIVAT" in key.upper():
        raise ValidationError(_('Private Key'))
    if key.strip() != key:
        raise ValidationError(_('Not trimmed'))
    if len(key) < 100:
        raise ValidationError(_('Not a key'))


@add_content
class PublicKey(BaseContent):
    names = ["PublicKey"]
    ctype = UserContentType.public.value

    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    note = models.TextField(max_length=100, default="", null=False, blank=True)
    hash = models.CharField(
        max_length=settings.MAX_HASH_SIZE, null=False, editable=False
    )

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", "Public Key")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_key = self.key

    def __str__(self):
        st = "{}...".format(self.hash[:10])
        split = self.key.rsplit(" ", 1)
        if len(split) == 2 and "@" in split[1]:
            st = split[1]
        if len(self.note) > 0:
            st = "{}: {}".format(st, self.note[:20])
        return st

    def render(self, **kwargs):
        from .forms import KeyForm
        if kwargs["scope"] == "hash":
            return self.hash
        elif kwargs["scope"] == "key":
            return self.key
        elif kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Public Key")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Public Key")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = KeyForm(
                uc=kwargs["uc"],
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                instance = kwargs["form"].save()
                kwargs["form"] = KeyForm(
                    uc=kwargs["uc"], instance=instance
                )
            template_name = "spider_base/full_form.html"
            if kwargs["scope"] == "update":
                template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            return render_to_string(
                "spider_keys/key.html", request=kwargs["request"],
                context=kwargs
            )

    def save(self, *args, **kwargs):
        if self.key and self.__original_key != self.key:
            h = hashlib.new(settings.KEY_HASH_ALGO)
            h.update(self.key.encode("ascii", "ignore"))
            self.hash = h.hexdigest()
        super().save(*args, **kwargs)
