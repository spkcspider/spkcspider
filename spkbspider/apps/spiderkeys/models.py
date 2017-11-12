from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy

from jsonfield import JSONField
import swapper

import hashlib
import logging

logger = logging.getLogger(__name__)


# Create your models here.

_htest = hashlib.new(settings.KEY_HASH_ALGO)
_htest.update(b"test")

if settings.MAX_HASH_SIZE > len(_htest.hexdigest()):
    raise Exception("MAX_HASH_SIZE too small to hold digest in hexadecimal")


class PublicKeyManager(models.Manager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def key_trimmed(val):
    if key.strip() != key:
        return False
    return True


def key_public(val):
    if "PRIVAT" in key.upper():
        return False
    return True

# also for account recovery
class AbstractPublicKey(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # don't check for similarity as the hash check will reveal all clashes
    key = models.TextField(editable=True, validators=[key_trimmed, key_public])
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    protected_by = models.ForeignKey(swapper.get_model_name('spider', 'UserComponent'), blank=True, null=True, default=None, related_name="publickeys")
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
