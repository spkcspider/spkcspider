__all__ = ["SpiderTagsConfig"]

from django.apps import AppConfig, apps
from .signals import UpdateDefaultLayouts
from spkcspider.apps.spider.helpers import extract_app_dicts
from spkcspider.apps.spider.signals import update_dynamic


class SpiderTagsConfig(AppConfig):
    name = 'spkcspider.apps.spider_tags'
    label = 'spider_tags'
    verbose_name = 'spkcspider tags optionally verified'

    def ready(self):
        from .fields import installed_fields
        for app in apps.get_app_configs():
            installed_fields.update(
                extract_app_dicts(app, "spider_tag_fields")
            )

        update_dynamic.connect(
            UpdateDefaultLayouts,
            dispatch_uid="update_default_layouts"
        )
