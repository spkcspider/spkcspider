__all__ = ["SpiderKeysConfig"]

from django.apps import AppConfig


class SpiderKeysConfig(AppConfig):
    name = 'spkcspider.apps.spider_keys'
    label = 'spider_keys'
    verbose_name = 'spkcspider keys, identifiers and anchors'
