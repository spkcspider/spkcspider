from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save, post_delete
from django.contrib.auth import get_user_model


class SpiderBaseConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spider_base'
    url_path = 'spider'
    url_namespace = 'spider_base'
    verbose_name = 'spkcspider base'

    def ready(self):
        from .signals import (
            UpdateSpiderCallback, InitUserCallback, DeleteContentCallback
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
        post_migrate.connect(
            UpdateSpiderCallback, sender=self,
            dispatch_uid="update_spkcspider"
        )
