__all__ = ["WebConfig"]

import posixpath

from django.db import models
from django.urls import reverse
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from spkcspider.apps.spider.constants.static import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.helpers import create_b64_token
# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_content
class WebConfig(BaseContent):
    appearances = [
        {
            "name": "WebConfig",
            "ctype": (
                VariantType.unique + VariantType.feature + VariantType.persist
            ),
            "strength": 0
        }
    ]

    config = models.TextField(default="", blank=True)

    @classmethod
    def action_urls(cls):
        return [
            ActionUrl(reverse("spider_webcfg:webconfig-view"), "webcfg")
        ]

    def get_size(self):
        return len(self.config)

    def get_priority(self):
        # low priority
        return -10

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["scope"] = kwargs["scope"]
        ret["user"] = kwargs["request"].user
        return ret

    def get_form(self, scope):
        from .forms import WebConfigForm as f
        return f

    def get_info(self):
        ret = super().get_info(unique=True)
        return "{}url={}\n".format(
            ret, self.associated.persist_token.referrer.replace("\n", "%0A")
        )


def ref_cache_path(instance, filename):
    ret = getattr(settings, "REFERENCE_FILE_DIR", "web_reference")
    size = getattr(settings, "FILE_NONCE_SIZE", 45)
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
            "ctype": (
                VariantType.feature
            ),
            "strength": 0
        },
        {
            "name": "WebPush",
            "ctype": (
                VariantType.feature
            ),
            "strength": 0
        }
    ]
    cache = models.FileField(
        upload_to=ref_cache_path, null=True, blank=True, help_text=_(
            "Cached/Frozen response"
        )
    )
    # can contain many filters
    source = models.URLField(max_length=800, null=True, blank=True)

    def clean(self):
        if self._associated_tmp:
            self._associated_tmp.content = self
        if not self.cache and not self.source:
            raise ValidationError(
                _('No data given'),
                code="no_data"
            )

        super().clean()
