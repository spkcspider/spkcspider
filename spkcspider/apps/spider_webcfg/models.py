__all__ = ["WebConfig"]


from django.db import models
from django.urls import reverse

from spkcspider.apps.spider.constants import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_content
class WebConfig(BaseContent):
    expose_name = False
    appearances = [
        {
            "name": "WebConfig",
            "ctype": (
                VariantType.unique + VariantType.component_feature +
                VariantType.persist
            ),
            "strength": 0
        }
    ]

    config = models.TextField(default="", blank=True)

    @classmethod
    def feature_urls(cls):
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
        return "{}url\x1f{}\x1e".format(
            ret, self.associated.persist_token.referrer.info_url
        )
