__all__ = ("Command",)

import json

from django.core.management.base import BaseCommand
from django.apps import apps


class Command(BaseCommand):
    help = (
        "fix json fields in string format"
    )

    def fix_instance(self, instance, field):
        if isinstance(getattr(instance, field), str):
            try:
                setattr(
                    instance,
                    field,
                    json.loads(
                        getattr(instance, field).replace("'", "\"")
                        .replace("False", "false")
                        .replace("True", "true")
                    )
                )
                self.stdout.write("Fixed instance: {}".format(instance))
            except Exception as exc:
                self.stdout.write(str(exc))
                self.stdout.write("\n")

    def handle(self, **options):
        from jsonfield import JSONField as step
        JSONField = type(step())

        for model in apps.get_models():
            requires_hack = []
            for field in model._meta.get_fields():
                if isinstance(field, JSONField):
                    requires_hack.append(field.name)
            if requires_hack:
                for i in model.objects.all():
                    for field in requires_hack:
                        self.fix_instance(i, field)
                    try:
                        i.clean()
                        i.save()
                    except Exception as exc:
                        self.stdout.write(str(exc))
                        self.stdout.write("\n")
