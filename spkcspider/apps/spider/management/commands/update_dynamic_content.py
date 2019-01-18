from django.core.management.base import BaseCommand
import logging


class Command(BaseCommand):
    help = 'Update dynamic spider content e.g. permissions, content'

    def handle(self, *args, **options):
        from spkcspider.apps.spider.signals import update_dynamic
        self.log = logging.getLogger(__name__)
        for handler in self.log.handlers:
            self.log.removeHandler(handler)
        self.log.addHandler(logging.StreamHandler(self.stdout))
        results = update_dynamic.send_robust(self)
        for (receiver, result) in results:
            if isinstance(result, Exception):
                self.log.error(
                    "%s failed", receiver, exc_info=result
                )
