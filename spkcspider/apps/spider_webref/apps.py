__all__ = ["SpiderWebRefConfig"]

from django.apps import AppConfig


class SpiderWebRefConfig(AppConfig):
    name = 'spkcspider.apps.spider_webref'
    label = 'spider_webref'
    spider_url_path = 'webref/'
    verbose_name = 'spkcspider Web references'
