import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .constants import (
    VERIFICATION_CHOICES
)


def dv_path(instance, filename):
    return 'dvfiles/{}/{}.{}'.format(
        datetime.datetime.now().strftime("%Y/%m"),
        instance.hash,
        "ttl"
    )


class VerifySourceObject(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    url = models.URLField(
        max_length=400, db_index=True, unique=True
    )
    get_params = models.TextField()

    def get_absolute_url(self):
        return "?".join((self.url, self.get_params))


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
    source = models.ForeignKey(
        VerifySourceObject, null=True, blank=True, on_delete=models.CASCADE
    )
    # url = models.URLField(max_length=600)
    data_type = models.CharField(default="layout", max_length=20)
    checked = models.DateTimeField(null=True, blank=True)
    verification_state = models.CharField(
        default="pending",
        max_length=10, choices=VERIFICATION_CHOICES
    )
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
