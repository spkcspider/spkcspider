
import enum

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.conf import settings

__all__ = (
    "add_content", "installed_contents", "BaseContent", "UserContentType"
)

installed_contents = {}


class UserContentType(str, enum.Enum):
    # not only private (index)
    public = "\x00"
    # has a seperate update, scope=update
    has_update = "\x01"
    # receives: request, scope, password


class add_content(object):
    def __init__(self, name=None):
        self.name = name

    def __call__(self, klass):
        name = self.name
        if not name:
            name = klass._meta.model_name
        if name in installed_contents:
            raise Exception("Duplicate content name")
        if name in getattr(settings, "BLACKLISTED_CONTENTS", {}):
            return klass
        installed_contents[name] = klass
        return klass


def initialize_protection_models():
    from .models import UserContentVariant
    for code, val in installed_contents.items():
        ret = UserContentVariant.objects.get_or_create(
            defaults={"ctype": val.ctype}, code=code
        )[0]
        if ret.ctype != val.ctype:
            ret.ctype = val.ctype
            ret.save()
    temp = UserContentVariant.objects.exclude(
        code__in=installed_contents.keys()
    )
    if temp.exists():
        print("Invalid content, please update or remove them:",
              [t.code for t in temp])


class BaseContent(models.Model):
    # for setup
    form_class = None

    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)

    id = models.BigAutoField(primary_key=True, editable=False)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated = GenericRelation("spider_base.UserContent")

    class Meta:
        abstract = True

    # for viewing
    def render(self, **kwargs):
        raise NotImplementedError

    def get_info(self, usercomponent):
        return "type=%s;" % self._meta.model_name
