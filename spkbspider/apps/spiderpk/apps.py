from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SpiderPKConfig(AppConfig):
    name = 'spkbspider.apps.spiderpk'
    label = 'spiderpk'
    verbose_name = 'SPKBSpider public keys and components'

    def ready(self):
        from .signals import InitProtectionsCallback
        post_migrate.connect(InitProtectionsCallback, sender=self, dispatch_uid="update_protections")
