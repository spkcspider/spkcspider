from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericRelation

from jsonfield import JSONField
import swapper

import hashlib
import logging

from spkbspider.apps.spider.models import UserComponentContent

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.KEY_HASH_ALGO)
_htest.update(b"test")

if settings.MAX_HASH_SIZE > len(_htest.hexdigest()):
    raise Exception("MAX_HASH_SIZE too small to hold digest in hexadecimal")


class PublicKeyManager(models.Manager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def valid_pkey_properties(val):
    if "PRIVAT" in key.upper():
        raise ValidationError(_('Private Key'))
    if key.strip() != key:
        raise ValidationError(_('Not trimmed'))
    if len(key) < 100:
        raise ValidationError(_('Not a key'))

# also for account recovery
class AbstractPublicKey(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # don't check for similarity as the hash check will reveal all clashes
    key = models.TextField(editable=True, validators=[valid_pkey_properties])
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    note = models.TextField(max_length=400, null=False)
    # can only be retrieved by hash or if it is the user
    # every hash has to be unique
    # TODO: people could steal public keys and block people from using service
    # needs key to mediate if clashes happen
    # don't use as primary key as algorithms could change
    # DON'T allow users to change hash
    hash = models.CharField(max_length=settings.MAX_HASH_SIZE, unique=True, null=False, editable=False)
    # allow admins editing to solve conflicts
    associated = GenericRelation(UserComponentContent)
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['hash']),
            models.Index(fields=['user']),
        ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_key = self.key

    def __str__(self):
        return self.hash

    def save(self, *args, **kwargs):
        if self.key and self.__original_key != self.key:
            h = hashlib.new(settings.KEY_HASH_ALGO)
            h.update(self.key.encode("utf-8", "ignore"))
            self.hash = h.hexdigest()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("spiderpk:pk-view", kwargs={"user":self.user.username, "hash":self.hash})

class PublicKey(AbstractPublicKey):
    class Meta:
        swappable = swapper.swappable_setting('spiderpk', 'PublicKey')
