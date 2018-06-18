from django.apps import AppConfig

from django.db.models.signals import pre_delete


def DeleteFilesCallback(sender, instance, **kwargs):
    instance.file.delete(False)


class SpiderFiletsConfig(AppConfig):
    name = 'spkcspider.apps.spider_filets'
    label = 'spider_filets'
    verbose_name = 'spkcspider File and Text content'

    def ready(self):
        from .models import FileFilet
        pre_delete.connect(
            DeleteFilesCallback, sender=FileFilet,
            dispatch_uid="delete_files_filet"
        )
