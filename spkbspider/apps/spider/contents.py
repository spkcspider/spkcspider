from django.db import models
from django.contrib.contenttypes.fields import GenericRelation

from .models import UserComponentContent

__all__ = ["add_content", "available_contenttypes", "BaseContent"]

available_contenttypes = {}

def add_content(klass):
    if klass in available_contenttypes:
        raise Exception("Duplicate content name")
    available_contenttypes[klass] = klass
    return klass

class BaseContent(models.Model)
    form = None
    view_template = None
    associated  = GenericRelation(UserComponentContent)
    class Meta:
        abstract = True
