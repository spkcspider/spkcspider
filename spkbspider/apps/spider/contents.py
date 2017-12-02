from django.db import models
from django.contrib.contenttypes.fields import GenericRelation

from .models import UserContent

__all__ = ["add_content", "available_contenttypes", "BaseContent"]

available_contenttypes = {}

def add_content(klass):
    if klass._meta.model_name in available_contenttypes:
        raise Exception("Duplicate content name")
    available_contenttypes[klass._meta.model_name] = klass
    return klass

class BaseContent(models.Model):
    form = None
    view_template = None

    id = models.BigAutoField(primary_key=True, editable=False)
    associated  = GenericRelation(UserContent)
    class Meta:
        abstract = True
