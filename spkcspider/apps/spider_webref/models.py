__all__ = ["WebReference"]

import posixpath

from django.db import models
# from django.urls import reverse
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from spkcspider.apps.spider.constants.static import VariantType
from spkcspider.apps.spider.helpers import create_b64_token
# from spkcspider.apps.spider.models.base import BaseInfoModel


def ref_cache_path(instance, filename):
    ret = getattr(settings, "REFERENCE_FILE_DIR", "web_reference")
    size = getattr(settings, "FILE_SALT_SIZE", 45)
    # try 100 times to find free filename
    # but should not take more than 1 try
    # IMPORTANT: strip . to prevent creation of htaccess files or similar
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.associated.usercomponent.user.pk),
                create_b64_token(size), filename.lstrip(".")
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise Exception("Unlikely event: no free filename")
    return ret_path


# @add_content
class WebReference():  # BaseContent, BaseInfoModel):
    appearances = [
        {
            "name": "WebReference",
            "ctype": VariantType.feature.value,
            "strength": 0
        }
    ]
    # real nonce
    nonce = models.CharField(max_length=40)
    tag = models.CharField(max_length=40)
    # Encrypted URI can contain many filters
    # Reason for encryption: protect level >=5 components, against server
    # breaches
    source = models.CharField(max_length=800, null=True, blank=True)
    cache = models.FileField(
        upload_to=ref_cache_path, null=True, blank=True, help_text=_(
            "Cached/Frozen response"
        )
    )

    def clean(self):
        if self._associated_tmp:
            self._associated_tmp.content = self
        if not self.cache and not self.source:
            raise ValidationError(
                _('No data given'),
                code="no_data"
            )
        super().clean()


class ReferenceMarker():
    reference = models.ForeignKey(
        WebReference, on_delete=models.CASCADE,
        related_name="markers", null=False, blank=False
    )
    key = models.ForeignKey(
        "spider_keys.PublicKey", on_delete=models.CASCADE,
        related_name="markers", null=False, blank=False,
        limit_choices_to={"use_for_encryption": True}
    )
    # encrypted symmetric key
    encrypted = models.CharField(max_length=200)


def get_email_path(instance, filename):
    ret = getattr(settings, "FILET_EMAIL_DIR", "email_filet")
    size = getattr(settings, "FILE_SALT_SIZE", 45)
    # try 100 times to find free filename
    # but should not take more than 1 try
    # IMPORTANT: strip . to prevent creation of htaccess files or similar
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.associated.usercomponent.user.pk),
                create_b64_token(size)
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise Exception("Unlikely event: no free filename")
    return ret_path


# @add_content
class EmailFilet:  # BaseContent):
    appearances = [
        {
            "name": "EmailFilet",
            "ctype": (
                VariantType.unlisted.value
            ),
            "strength": 0
        }
    ]

    nonce = models.CharField(max_length=40)
    tag = models.CharField(max_length=40)

    stored = models.FileField(
        upload_to=get_email_path, null=False, blank=False
    )
