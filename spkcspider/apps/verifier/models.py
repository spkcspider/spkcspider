import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from jsonfield import JSONField

from .constants import (
    VERIFICATION_CHOICES
)


def dv_path(instance, filename):
    return 'dvfiles/{}/{}.{}'.format(
        datetime.datetime.now().strftime("%Y/%m"),
        instance.hash,
        "ttl"
    )


class DataVerificationTag(models.Model):
    """ Contains verified data """
    # warning: never depend directly on user, seperate for multi-db setups
    id = models.BigAutoField(primary_key=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    hash = models.SlugField(
        unique=True, db_index=True, null=False, max_length=512
    )
    dvfile = models.FileField(
        upload_to=dv_path, null=True, blank=True, help_text=_(
            "File with data to verify"
        )
    )
    data_type = models.CharField(default="layout", max_length=20)
    checked = models.DateTimeField(null=True, blank=True)
    verification_state = models.CharField(
        default="pending",
        max_length=10, choices=VERIFICATION_CHOICES
    )
    linked_hashes = JSONField(default={}, blank=True)
    note = models.TextField(default="", blank=True)

    class Meta:
        permissions = [("can_verify", "Can verify Data Tag?")]

    def __str__(self):
        return "DVTag: ...%s" % self.hash[:30]

    def get_absolute_url(self):
        return reverse(
            "spider_verifier:verify",
            kwargs={
                "hash": self.hash
            }
        )
