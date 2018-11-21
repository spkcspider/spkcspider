__all__ = ["SpiderVerifierConfig"]

from django.apps import AppConfig
from django.conf import settings


class SpiderVerifierConfig(AppConfig):
    name = 'spkcspider.apps.verifier'
    label = 'spider_verifier'
    verbose_name = 'spkcspider verifier'
    if getattr(settings, "AUTO_INCLUDE_VERIFIER", False):
        spider_url_path = 'verify/'
