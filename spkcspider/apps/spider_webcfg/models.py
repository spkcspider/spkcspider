__all__ = ["WebConfig"]

from django.db import models
from spkcspider.apps.spider.contents import BaseContent

# from ..constants import MAX_NONCE_SIZE, hex_size_of_bigid


class WebConfig(BaseContent):

    # key = models.SlugField(
    #     max_length=(MAX_NONCE_SIZE*4//3)+hex_size_of_bigid,
    #     db_index=True
    # )
    url = models.URLField(max_length=800)
    config = models.TextField(default="", blank=True)

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["scope"] = kwargs["scope"]
        ret["user"] = kwargs["request"].user
        return ret

    def get_form(self, scope):
        from .forms import WebConfigForm as f
        return f

    def get_info(self):
        ret = super().get_info(primary=True)
        return "{}url={}\n".format(
            ret, self.url.replace("\n", "%0A")
        )
