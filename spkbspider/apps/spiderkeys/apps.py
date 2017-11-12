from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SpiderKeysConfig(AppConfig):
    name = 'spkbspider.apps.spiderkeys'
    label = 'spiderkeys'
    verbose_name = 'SPKBSpider public keys'
