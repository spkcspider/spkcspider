from django.apps import AppConfig
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model


class SpiderAccountsConfig(AppConfig):
    name = 'spkcspider.apps.spider_accounts'
    label = 'spider_accounts'
    verbose_name = 'Spkcspider User Model'
    url_namespace = "auth"
    url_path = "accounts/"

    def ready(self):
        from .signals import SetupUserCallback
        post_save.connect(
            SetupUserCallback, sender=get_user_model(),
            dispatch_uid="initial_setup_user"
        )
