from django.apps import AppConfig


class SpiderPKConfig(AppConfig):
    name = 'spkbspider.apps.spiderpk'
    label = 'spiderpk'
    verbose_name = 'SPKBSpider public keys and components'

    def ready(self):
        import spkbspider.apps.spiderpk.signals_init
