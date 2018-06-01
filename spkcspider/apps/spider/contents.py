
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
    raw_update = "\x02"


def add_content(klass):
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
        variant = UserContentVariant.objects.get_or_create(
            defaults={"ctype": val.ctype, "raw": val.raw}, code=code
        )[0]
        if variant.ctype != val.ctype:
            variant.ctype = val.ctype
        if variant.raw != val.raw:
            variant.raw = val.raw
        variant.save()
    temp = UserContentVariant.objects.exclude(
        code__in=installed_contents.keys()
    )
    if temp.exists():
        print("Invalid content, please update or remove them:",
              [t.code for t in temp])


class BaseContent(models.Model):
    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)

    id = models.BigAutoField(primary_key=True, editable=False)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated = GenericRelation("spider_base.UserContent")

    # if static_create is used and class not saved yet
    kwargs = None

    class Meta:
        abstract = True

    @classmethod
    def static_create(cls, **kwargs):
        self = cls()
        self.kwargs = kwargs
        return self

    def __str__(self):
        if not self.id:
            return "%s: -" % self.kwargs["code"]
        return "%s: %i" % (self.associated.ctype, self.id)

    # for viewing
    def render(self, **kwargs):
        raise NotImplementedError

    def get_info(self, usercomponent):
        return "type=%s;" % self._meta.model_name
