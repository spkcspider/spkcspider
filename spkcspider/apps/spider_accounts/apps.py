__all__ = ["SpiderAccountsConfig"]

from django.apps import AppConfig


class SpiderAccountsConfig(AppConfig):
    name = 'spkcspider.apps.spider_accounts'
    label = 'spider_accounts'
    verbose_name = 'Spkcspider User Model'
    spider_url_path = "accounts/"
