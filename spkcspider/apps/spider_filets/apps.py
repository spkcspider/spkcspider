__all__ = ["SpiderFiletsConfig"]

from django.apps import AppConfig

from django.db.models.signals import post_delete


def DeleteFilesCallback(sender, instance, **kwargs):
    instance.file.delete(False)


class SpiderFiletsConfig(AppConfig):
    name = 'spkcspider.apps.spider_filets'
    label = 'spider_filets'
    verbose_name = 'spkcspider File and Text content'

    def ready(self):
        from .models import FileFilet
        post_delete.connect(
            DeleteFilesCallback, sender=FileFilet,
            dispatch_uid="delete_files_filet"
        )
