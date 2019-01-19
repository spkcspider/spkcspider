__all__ = ["SpiderVerifierConfig"]

from django.apps import AppConfig


class SpiderVerifierConfig(AppConfig):
    name = 'spkcspider.apps.verifier'
    label = 'spider_verifier'
    verbose_name = 'spkcspider verifier'
    spider_url_path = 'verify/'
