__all__ = ["SpiderBaseConfig"]

from django.apps import AppConfig
from django.db.models.signals import (
    post_migrate, post_save, pre_save, post_delete
)
from django.contrib.auth.signals import user_logged_out
from django.contrib.auth import get_user_model
from django.conf import settings
from .helpers import extract_app_dicts
from .signals import (
    UpdateSpiderCb, InitUserCb, UpdateAnchorContent,
    UpdateAnchorComponent, update_dynamic, TriggerUpdate, RemoveTokensLogout,
    CleanupCb, MovePersistentCb, move_persistent, DeleteContentCb,
    UpdateAnchorTargets
)


class SpiderBaseConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spider_base'
    spider_url_path = 'spider/'
    verbose_name = 'spkcspider base'

    def ready(self):
        from .models import (
            AssignedContent, UserComponent, AuthToken, LinkContent
        )
        from django.apps import apps
        from .protections import installed_protections

        for app in apps.get_app_configs():
            installed_protections.update(
                extract_app_dicts(app, "spider_protections", "name")
            )

        user_logged_out.connect(
            RemoveTokensLogout, dispatch_uid="delete_token_logout"
        )
        pre_save.connect(
            UpdateAnchorComponent, sender=UserComponent,
            dispatch_uid="spider_update_anchors_component"
        )
        pre_save.connect(
            UpdateAnchorTargets, sender=UserComponent,
            dispatch_uid="spider_update_anchors_targets"
        )
        post_save.connect(
            UpdateAnchorContent, sender=AssignedContent,
            dispatch_uid="spider_update_anchors_content"
        )
        move_persistent.connect(
            MovePersistentCb, sender=AuthToken,
            dispatch_uid="spider_move_persistent"
        )

        # order important for next two
        post_delete.connect(
            CleanupCb, sender=UserComponent,
            dispatch_uid="spider_delete_cleanup_usercomponent"
        )

        post_delete.connect(
            CleanupCb, sender=AssignedContent,
            dispatch_uid="spider_delete_cleanup_content"
        )

        post_delete.connect(
            DeleteContentCb, sender=LinkContent,
            dispatch_uid="spider_delete_cleanup_linkcontent"
        )

        #####################

        post_save.connect(
            InitUserCb, sender=get_user_model(),
            dispatch_uid="setup_spider_user"
        )

        update_dynamic.connect(
            UpdateSpiderCb,
            dispatch_uid="update_spider_dynamic"
        )

        if getattr(settings, "UPDATE_DYNAMIC_AFTER_MIGRATION", True):
            post_migrate.connect(
                TriggerUpdate, sender=self,
                dispatch_uid="update_spider_base_trigger"
            )
