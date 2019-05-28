__all__ = ["WebConfig"]


from django.db import models
from django.urls import reverse
from django.utils.translation import pgettext

from spkcspider.apps.spider.constants import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_content
class WebConfig(BaseContent):
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

    config = models.TextField(default="", blank=True)

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
            ActionUrl(reverse("spider_webcfg:webconfig-view"), "webcfg")
        ]

    def get_size(self):
        return super().get_size() + len(self.config)

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
        # persistent tokens automatically enforce uniqueness
        ret = super().get_info(
            unique=(self.associated.attached_to_token.persist < 0)
        )
        return "{}url={}\x1e".format(
            ret, self.associated.attached_to_token.referrer.url
        )
