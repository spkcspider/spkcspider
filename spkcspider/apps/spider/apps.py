from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save
from django.contrib.auth import get_user_model


class SpiderBaseConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spider_base'
    url_path = 'spider'
    url_namespace = 'spider_base'
    verbose_name = 'spkcspider base'

    def ready(self):
        from .signals import (
            UpdateSpiderCallback, InitUserCallback
        )
        from .contents import initialize_ratelimit
        initialize_ratelimit()

        post_save.connect(
            InitUserCallback, sender=get_user_model(),
            dispatch_uid="initial_user"
        )
        post_migrate.connect(
            UpdateSpiderCallback, sender=self,
            dispatch_uid="update_spkcspider"
        )
