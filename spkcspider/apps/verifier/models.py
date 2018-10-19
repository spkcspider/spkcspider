import datetime

from django.db import models

from .constants import (
    VERIFICATION_CHOICES
)


def dv_path(instance, filename):
    return 'dvfiles/{0}/{1}'.format(
        datetime.datetime.now().strftime("%Y/%m"),
        instance.hash
    )


class DataVerificationTag(models.Model):
    """ Contains verified data """
    # warning: never depend directly on user, seperate for multi-db setups
    id = models.BigAutoField(primary_key=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    hash = models.TextField(
        unique=True, db_index=True, null=False
    )
    dvfile = models.FileField(upload_to=dv_path, null=True, blank=True)
    checked = models.DateTimeField(default=None, null=True)
    anchor = models.TextField(
        default=None, null=True
    )
    data_type = models.CharField(
        default="layout",
        max_length=20,
    )
    verification_state = models.CharField(
        default="pending",
        max_length=10, choices=VERIFICATION_CHOICES
    )
