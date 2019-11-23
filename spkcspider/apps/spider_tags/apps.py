__all__ = ["SpiderTagsConfig"]

from django.apps import AppConfig
from spkcspider.apps.spider.signals import update_dynamic

from .signals import UpdateLayouts


class SpiderTagsConfig(AppConfig):
    name = 'spkcspider.apps.spider_tags'
    label = 'spider_tags'
    spider_url_path = 'spidertags/'
    spider_layouts_path = ".layouts"
    spider_fields_path = ".fields"
    verbose_name = 'spkcspider tags'

    def ready(self):
        update_dynamic.connect(
            UpdateLayouts,
            dispatch_uid="update_layouts"
        )
