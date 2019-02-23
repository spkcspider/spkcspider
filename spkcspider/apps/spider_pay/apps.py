__all__ = ["SpiderPayConfig"]

from django.apps import AppConfig


class SpiderPayConfig(AppConfig):
    name = 'spkcspider.apps.spider_pay'
    label = 'spider_pay'
    spider_url_path = 'spiderpay/'
    verbose_name = 'spkcspider Payments'
