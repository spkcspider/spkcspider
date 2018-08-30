from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save, post_delete
from django.contrib.auth import get_user_model
import logging


def TriggerUpdate(sender, **_kwargs):
    from .signals import update_spider
    results = update_spider.send_robust(sender)
    for (receiver, result) in results:
        if isinstance(result, Exception):
            logging.exception(result)


class SpiderBaseConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spider_base'
    url_path = 'spider/'
    url_namespace = 'spider_base'
    verbose_name = 'spkcspider base'

    def ready(self):
        from django.conf import settings
        from .signals import (
            UpdateSpiderCallback, InitUserCallback, DeleteContentCallback,
            update_dynamic
        )
        from .models import (
            AssignedContent
        )
        from .contents import initialize_ratelimit
        initialize_ratelimit()

        post_delete.connect(
            DeleteContentCallback, sender=AssignedContent,
            dispatch_uid="delete_content"
        )

        post_save.connect(
            InitUserCallback, sender=get_user_model(),
            dispatch_uid="initial_user"
        )

        update_dynamic.connect(
            UpdateSpiderCallback,
            dispatch_uid="update_spider_base"
        )

        if getattr(settings, "UPDATE_DYNAMIC_AFTER_MIGRATION", True):
            post_migrate.connect(
                TriggerUpdate, sender=self,
                dispatch_uid="update_spider_base_trigger"
            )
