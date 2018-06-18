
import enum
import time
from importlib import import_module

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.conf import settings
from django.utils.translation import pgettext
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.http import Http404

__all__ = (
    "add_content", "installed_contents", "BaseContent", "UserContentType",
    "rate_limit_func", "initialize_ratelimit"
)

installed_contents = {}


def rate_limit_default(view, request):
    time.sleep(1)
    raise Http404()


rate_limit_func = None


class UserContentType(str, enum.Enum):
    # not only private (index)
    public = "a"
    # update is without form/for form updates it is not rendered
    raw_update = "b"
    # adding renders no form, only content
    raw_add = "c"


def add_content(klass):
    name = klass._meta.model_name
    if name in installed_contents:
        raise Exception("Duplicate content name")
    if name in getattr(settings, "BLACKLISTED_CONTENTS", {}):
        return klass
    installed_contents[name] = klass
    return klass


def initialize_ratelimit():
    global rate_limit_func
    func = getattr(settings, "RATELIMIT_FUNC_CONTENTS", None)
    if callable(func):
        rate_limit_func = func
    elif isinstance(func, str):
        func = func.rsplit(".", 1)
        func = getattr(import_module(func[0]), func[1])
        rate_limit_func = func
    else:
        rate_limit_func = rate_limit_default


def initialize_content_models(apps=None):
    if not apps:
        from django.apps import apps
    UserContentVariant = apps.get_model("spider_base", "UserContentVariant")
    all_content = models.Q()
    for code, val in installed_contents.items():
        names = val.names
        if callable(names):
            names = names()

        update = False
        if len(names) == 1:
            update = True
        for n in names:
            if update:
                variant = UserContentVariant.objects.get_or_create(
                    defaults={"ctype": val.ctype, "name": n}, code=code
                )[0]
            else:
                variant = UserContentVariant.objects.get_or_create(
                    defaults={"ctype": val.ctype}, code=code, name=n
                )[0]
            if variant.ctype != val.ctype:
                variant.ctype = val.ctype
            if variant.name != n:
                variant.name = n
            variant.save()
            all_content |= models.Q(name=n, code=code)
    temp = UserContentVariant.objects.exclude(all_content)
    if temp.exists():
        print("Invalid content, please update or remove them:",
              [t.code for t in temp])


class BaseContent(models.Model):
    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)
    # iterable or callable with names under which content should appear
    names = None
    ctype = ""
    # is info unique for usercomponent
    is_unique = False

    id = models.BigAutoField(primary_key=True, editable=False)
    # every content can specify its own deletion period
    deletion_period = getattr(settings, "DELETION_PERIOD_CONTENT", None)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated_rel = GenericRelation("spider_base.UserContent")
    _associated2 = None

    @property
    def associated(self):
        if self._associated2:
            return self._associated2
        return self.associated_rel.first()

    @property
    def is_protected(self):
        # TODO: add good logic, this way is_protected is unsafe to use
        return False

    # if static_create is used and class not saved yet
    kwargs = None

    class Meta:
        abstract = True

    @classmethod
    def static_create(cls, associated=None, **kwargs):
        ob = cls()
        if associated:
            ob._associated2 = associated
        ob.kwargs = kwargs
        return ob

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", name)

    def __str__(self):
        if not self.id:
            _id = "-"
        else:
            _id = self.id
        return "%s: %s" % (self.localize_name(self.associated.ctype.name), _id)

    def __repr__(self):
        return "<Content: %s>" % self.__str__()

    def is_owner(self, user):
        return user == self.associated.usercomponent.user

    # for viewing
    def render(self, **kwargs):
        raise NotImplementedError

    def get_form_kwargs(self, request):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {"instance": self}

        if request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': request.POST,
                'files': request.FILES,
            })
        return kwargs

    def get_info(self, usercomponent):
        # id is from UserContent
        if not self.is_unique:
            return "uc=%s;code=%s;name=%s;id=%s;" % \
                (
                    usercomponent.name,
                    self._meta.model_name,
                    self.associated.ctype.name,
                    self.associated.id
                )
        else:
            return "uc=%s;code=%s;name=%s;" % \
                (
                    usercomponent.name,
                    self._meta.model_name,
                    self.associated.ctype.name
                )

    def clean(self):
        from .models import UserContent
        if self._associated2:
            self._associated2.content = self
        a = self.associated
        a.info = self.get_info(a.usercomponent)
        try:
            if UserContent.objects.get(info=a.info).id != a.id:
                raise ValidationError(
                        message=_('Duplicate content per component (content '
                                  'type allows only single content)'),
                        code='duplicate content',
                    )
        except UserContent.DoesNotExist:
            pass

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)
        a = self.associated
        a.info = self.get_info(a.usercomponent)
        if self._associated2:
            a.content = self
        # update info and set content
        a.save()
        return ret
