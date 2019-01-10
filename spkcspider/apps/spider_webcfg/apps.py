__all__ = ["SpiderWebCfgConfig"]

from django.apps import AppConfig


class SpiderWebCfgConfig(AppConfig):
    name = 'spkcspider.apps.spider_webcfg'
    label = 'spider_webcfg'
    spider_url_path = 'webcfg/'
    verbose_name = 'spkcspider WebConfig'
    spider_features = {
        "webconfig": "spkcspider.apps.spider_webcfg.models.WebConfig"
    }

    def ready(self):
        from spkcspider.apps.spider.signals import remote_account_deletion
        from .signals import DeleteAssociatedWebCfg
        remote_account_deletion.connect(
            DeleteAssociatedWebCfg, dispatch_uid="delete_associated_webcfg"
        )
