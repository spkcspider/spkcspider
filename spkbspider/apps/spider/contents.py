from django.db import models
from django.contrib.contenttypes.fields import GenericRelation

from .models import UserContent

__all__ = ["add_content", "installed_contents", "allowed_search_fields", "BaseContent"]

installed_contents = {}

def add_content(klass):
    if klass._meta.model_name in installed_contents:
        raise Exception("Duplicate content name")
    if klass._meta.model_name in getattr(settings, "BLACKLISTED_CONTENTS", {}):
        return klass
    installed_contents[klass._meta.model_name] = klass
    return klass

class BaseContent(models.Model):
    # for setup
    form_class = None

    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user and legitimated users (if not index)

    id = models.BigAutoField(primary_key=True, editable=False)
    associated = GenericRelation(UserContent)
    class Meta:
        abstract = True

    # for viewing
    def render(self, **kwargs):
        raise NotImplementedError

    def get_info(self, usercomponent):
        return "type=%s;" % self._meta.model_name
