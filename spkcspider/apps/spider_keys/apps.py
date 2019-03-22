__all__ = ["SpiderKeysConfig"]

from django.apps import AppConfig


class SpiderKeysConfig(AppConfig):
    name = 'spkcspider.apps.spider_keys'
    label = 'spider_keys'
    spider_url_path = 'spiderkeys/'
    verbose_name = 'spkcspider keys, identifiers and anchors'
