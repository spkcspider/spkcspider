__all__ = ["SpiderBaseConfig"]

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import (
    m2m_changed, post_delete, post_migrate, post_save, pre_save
)

from .signals import (
    CleanupCb, InitUserCb, TriggerUpdate, UpdateAnchorComponentCb,
    UpdateComponentFeaturesCb, UpdateContentCb, UpdateContentFeaturesCb,
    UpdateSpiderCb, update_dynamic
)


class SpiderBaseConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spider_base'
    spider_url_path = 'spider/'
    spider_protections_path = ".protections"
    verbose_name = 'spkcspider base'

    def ready(self):
        from .models import (
            AssignedContent, UserComponent
        )

        pre_save.connect(
            UpdateAnchorComponentCb, sender=UserComponent,
        )
        post_save.connect(
            UpdateContentCb, sender=AssignedContent,
        )
        m2m_changed.connect(
            UpdateComponentFeaturesCb, sender=UserComponent.features.through
        )
        m2m_changed.connect(
            UpdateContentFeaturesCb, sender=AssignedContent.features.through,
        )

        # order important for next two
        post_delete.connect(
            CleanupCb, sender=UserComponent,
        )

        post_delete.connect(
            CleanupCb, sender=AssignedContent,
        )

        #####################

        post_save.connect(
            InitUserCb, sender=get_user_model(),
        )

        update_dynamic.connect(
            UpdateSpiderCb,
            dispatch_uid="update_spider_dynamic"
        )

        if getattr(settings, "UPDATE_DYNAMIC_AFTER_MIGRATION", True):
            post_migrate.connect(
                TriggerUpdate, sender=self,
            )
