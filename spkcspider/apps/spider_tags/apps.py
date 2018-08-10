from django.apps import AppConfig
from django.db.models.signals import post_migrate
from .signals import UpdateDefaultLayouts


class SpiderTagsConfig(AppConfig):
    name = 'spkcspider.apps.spider_tags'
    label = 'spider_tags'
    verbose_name = 'spkcspider tags optionally verified'

    def ready(self):
        from django.apps import apps
        from .fields import valid_fields
        for app in apps.get_app_configs():
            tags = getattr(app, "spider_tag_fields", {})
            valid_fields.update(tags)
        post_migrate.connect(
            UpdateDefaultLayouts, sender=self,
            dispatch_uid="update_default_layouts"
        )
