from django.db import models
from django.contrib.contenttypes.fields import GenericRelation

from .models import UserContent

__all__ = ["add_content", "installed_contents", "BaseContent"]

installed_contents = {}

def add_content(klass):
    if klass._meta.model_name in installed_contents:
        raise Exception("Duplicate content name")
    if klass._meta.model_name in getattr(settings, "BLACKLISTED_CONTENTS", {}):
        return klass
    installed_contents[klass._meta.model_name] = klass
    return klass

class BaseContent(models.Model):
    form = None
    view_template = None

    id = models.BigAutoField(primary_key=True, editable=False)
    associated  = GenericRelation(UserContent)
    class Meta:
        abstract = True
