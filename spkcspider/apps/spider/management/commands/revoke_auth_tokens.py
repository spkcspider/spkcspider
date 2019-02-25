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
        parser.add_argument(
            '--referrer', action='store', dest='referrer', default=None,
            help='Delete tokens of referrer',
        )
        parser.add_argument(
            '--anchor', action='store', dest='anchor', default=None,
            help=(
                'Delete tokens of anchor id:\n'
                '0/"component" for component,\n'
                '"all":  all tokens,\n'
                '"persist": persistent tokens'
            ),
        )

    def handle(self, oldest=None, days=None, anchor=None, **options):
        from spkcspider.apps.spider.models import AuthToken
        q = AuthToken.objects.all()

        if options['referrer']:
            q = q.filter(referrer__url=options["referrer"])
            if anchor == "all" or not anchor:
                pass
            elif anchor == "component":
                q = q.filter(persist=0)
            elif anchor == "persist":
                q = q.filter(persist__gte=0)
            else:
                q = q.filter(persist=int(anchor))
        elif anchor == "component":
            q = q.filter(persist=0)
        elif anchor == "persist":
            q = q.filter(persist__gte=0)
        elif anchor == "all":
            pass
        elif anchor:
            q = q.filter(persist=int(anchor))
        else:
            q = q.filter(persist=-1)
        if days:
            dt = datetime.datetime.now() - \
                datetime.timedelta(days=int(days))
            q.filter(created__lt=dt)
        if oldest:
            # create list with ids
            ids = q.order_by("created").values_list(
                'id', flat=True
            )[:int(oldest)]
            # recreate Query
            q = AuthToken.objects.filter(id__in=ids)
        self.stdout.write("count: %s\n" % q.delete()[0])
