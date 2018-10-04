__all__ = ("Command",)

import datetime
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Delete old/all auth tokens"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', action='store', dest='days', default=None,
            help='Delete tokens older than days',
        )
        parser.add_argument(
            '--oldest', action='store', dest='oldest', default=None,
            help='Delete oldest x tokens',
        )

    def handle(self, **options):
        from spkcspider.apps.spider.models import AuthToken
        q = AuthToken.objects.all()
        if options['days']:
            dt = datetime.datetime.now() - \
                datetime.timedelta(days=int(options['days']))
            q.filter(created__lt=dt)
        if options['oldest']:
            ids = q.order_by("created").values_list(
                'id', flat=True
            )[:int(options['oldest'])]
            q = AuthToken.objects.filter(id__in=ids)
        print(q.delete()[0])
