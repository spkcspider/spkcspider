from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SpiderUCConfig(AppConfig):
    name = 'spkbspider.apps.spider'
    label = 'spider'
    verbose_name = 'SPKBSpider user components (Basis)'

    def ready(self):
        from .signals import InitProtectionsCallback
        post_migrate.connect(InitProtectionsCallback, sender=self, dispatch_uid="update_protections")
