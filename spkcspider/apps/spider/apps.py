from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save
from django.contrib.auth import get_user_model


class SpiderUCConfig(AppConfig):
    name = 'spkcspider.apps.spider'
    label = 'spiderucs'
    verbose_name = 'spkcspider base'

    def ready(self):
        from .signals import (
            InitProtectionsCallback, InitUserComponentsCallback
        )
        post_migrate.connect(InitProtectionsCallback, sender=self,
                             dispatch_uid="update_protections")
        post_save.connect(InitUserComponentsCallback, sender=get_user_model(),
                          dispatch_uid="initial_usercomponents")
