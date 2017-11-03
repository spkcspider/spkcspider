from django.apps import AppConfig


class SpiderAccountsConfig(AppConfig):
    name = 'spkbspider.apps.spideraccounts'
    label = 'spideraccounts'
    verbose_name = 'SPKBSpider user implementation'

    def ready(self):
        import spkbspider.apps.spideraccounts.signals_init
