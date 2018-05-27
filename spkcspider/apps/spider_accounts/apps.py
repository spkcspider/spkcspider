from django.apps import AppConfig
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model


class SpiderAccountsConfig(AppConfig):
    name = 'spkcspider.apps.spider_accounts'
    label = 'spider_accounts'
    verbose_name = 'User and authentication implementation suitable for spkcspider'

    def ready(self):
        from .signals import InitialGrantsCallback
        post_save.connect(
            InitialGrantsCallback, sender=get_user_model(),
            dispatch_uid="initial_grants_user"
        )
