
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
    # update is without form/for form updates it is not rendered
    raw_update = "\x01"
    # adding renders no form, only content
    raw_add = "\x02"


def add_content(klass):
    name = klass._meta.model_name
    if name in installed_contents:
        raise Exception("Duplicate content name")
    if name in getattr(settings, "BLACKLISTED_CONTENTS", {}):
        return klass
    installed_contents[name] = klass
    return klass


def initialize_content_models():
    from .models import UserContentVariant
    for code, val in installed_contents.items():
        n = val.content_name
        if not n:
            n = val.__name__
        variant = UserContentVariant.objects.get_or_create(
            defaults={"ctype": val.ctype, "name": n}, code=code
        )[0]
        if variant.ctype != val.ctype:
            variant.ctype = val.ctype
        if variant.name != n:
            variant.name = n
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
    content_name = None
    ctype = ""

    id = models.BigAutoField(primary_key=True, editable=False)
    # every content can specify its own deletion period
    deletion_period = getattr(settings, "DELETION_PERIOD_CONTENT", None)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated = GenericRelation("spider_base.UserContent")

    # if static_create is used and class not saved yet
    kwargs = None

    class Meta:
        abstract = True

    @classmethod
    def static_create(cls, associated=None, **kwargs):
        self = cls(associated=associated)
        self.kwargs = kwargs
        return self

    def __str__(self):
        if not self.id:
            _id = "-"
        else:
            _id = self.id
        return "%s: %s" % (self.associated.ctype.name, _id)

    # for viewing
    def render(self, **kwargs):
        raise NotImplementedError

    def get_form_kwargs(self, request, initial=None, prefix=None):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            'initial': initial if initial else {},
            'prefix': prefix,
        }

        if request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': request.POST,
                'files': request.FILES,
            })
        return kwargs

    def get_info(self, usercomponent):
        return "code=%s;name=%s;" % \
            (
                self._meta.model_name,
                self.associated.ctype.name
            )
