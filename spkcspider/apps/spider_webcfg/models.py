__all__ = ["WebConfig"]

from django.urls import reverse
from django.utils.translation import pgettext
from spkcspider.apps.spider.models import DataContent
from spkcspider.apps.spider import registry
from spkcspider.constants import ActionUrl, VariantType
from spkcspider.utils.fields import add_by_field

# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_by_field(registry.contents, "_meta.model_name")
class WebConfig(DataContent):
    expose_name = False
    appearances = [
        {
            # only one per domain
            "name": "WebConfig",
            "ctype": (
                VariantType.unique + VariantType.component_feature +
                VariantType.persist
            ),
            "strength": 0
        },
        {
            # only one per domain, times out, don't require user permission
            "name": "TmpConfig",
            "ctype": (
                VariantType.unique + VariantType.component_feature +
                VariantType.domain_mode
            ),
            "strength": 5
        }
    ]

    class Meta:
        proxy = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        if name == "TmpConfig":
            return _("content name", "Temporary Web Configuration")
        else:
            return _("content name", "Web Configuration")

    def get_content_name(self):
        return self.associated.attached_to_token.referrer.url[:255]

    @classmethod
    def feature_urls(cls, name):
        return [
            ActionUrl("webcfg", reverse("spider_webcfg:webconfig-view"))
        ]

    def get_size(self, prepared_attachements=None):
        # ensure space for at least 100 bytes (for free)
        ret = super().get_size(prepared_attachements)
        # hacky, use default values, TODO: improve
        ret = max(255, ret - 255 + 100)
        return ret

    def get_priority(self):
        # low priority
        return -10

    def get_form(self, scope):
        from .forms import WebConfigForm as f
        return f

    def get_info(self):
        # persistent tokens automatically enforce uniqueness
        ret = super().get_info(
            unique=(self.associated.attached_to_token.persist < 0)
        )
        return "{}url={}\x1e".format(
            ret, self.associated.attached_to_token.referrer.url
        )
