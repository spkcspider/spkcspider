from django.core.management.base import BaseCommand
import logging


class Command(BaseCommand):
    help = 'Update dynamic spider content e.g. permissions, content'

    def handle(self, *args, **options):
        from spkcspider.apps.spider.signals import update_dynamic
        results = update_dynamic.send_robust(self)
        for (receiver, result) in results:
            if isinstance(result, Exception):
                logging.exception(result)
