from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string


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
    content_name = "PublicKey"
    ctype = UserContentType.public.value

    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    note = models.TextField(max_length=100, default="", null=False)
    hash = models.CharField(
        max_length=settings.MAX_HASH_SIZE, null=False, editable=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_key = self.key

    def __str__(self):
        return "{}: {}".format(self.hash, self.note)

    def render(self, **kwargs):
        from .forms import KeyForm
        if kwargs["scope"] == "hash":
            return self.hash
        elif kwargs["scope"] == "key":
            return self.key
        elif kwargs["scope"] in ["update", "add"]:
            kwargs["form"] = KeyForm(
                uc=kwargs["uc"],
                **self.get_form_kwargs(kwargs["request"])
            )
            if self.id:
                kwargs["legend"] = _("Update Public Key")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Public Key")
                kwargs["confirm"] = _("Create")
            return render_to_string(
                "spider_base/full_form.html", request=kwargs["request"],
                context=kwargs
            )

    def save(self, *args, **kwargs):
        if self.key and self.__original_key != self.key:
            h = hashlib.new(settings.KEY_HASH_ALGO)
            h.update(self.key.encode("ascii", "ignore"))
            self.hash = h.hexdigest()
        super().save(*args, **kwargs)
