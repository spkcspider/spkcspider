
__all__ = (
    "add_content", "installed_contents", "BaseContent",
    "rate_limit_func", "initialize_ratelimit"
)

import time
import os
import zipfile
import tempfile
import json
from collections import OrderedDict
from importlib import import_module

from django.apps import apps as django_apps
from django.db import models
from django.utils.translation import gettext
from django.core.exceptions import NON_FIELD_ERRORS
from django.template.loader import render_to_string
from django.core.files.base import File

from django.contrib.contenttypes.fields import GenericRelation
from django.http import FileResponse, JsonResponse
from django.conf import settings
from django.utils.translation import pgettext
from django.http import Http404

from .constants import UserContentType


installed_contents = {}


def rate_limit_default(view, request):
    time.sleep(1)
    raise Http404()


rate_limit_func = None


def add_content(klass):
    code = klass._meta.model_name
    if code in installed_contents:
        raise Exception("Duplicate content")
    if code in getattr(settings, "BLACKLISTED_CONTENTS", {}):
        return klass
    installed_contents[code] = klass
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
        apps = django_apps
    ContentVariant = apps.get_model("spider_base", "ContentVariant")
    all_content = models.Q()
    for code, val in installed_contents.items():
        appearances = val.appearances
        if callable(appearances):
            appearances = appearances()

        # update name if only one name exists
        update = False
        if len(appearances) == 1:
            update = True
        for (n, ctype) in appearances:
            if update:
                variant = ContentVariant.objects.get_or_create(
                    defaults={"ctype": ctype, "name": n}, code=code
                )[0]
            else:
                variant = ContentVariant.objects.get_or_create(
                    defaults={"ctype": ctype}, code=code, name=n
                )[0]
            if variant.ctype != ctype:
                variant.ctype = ctype
            if variant.name != n:
                variant.name = n
            variant.save()
            all_content |= models.Q(name=n, code=code)
    invalid_models = ContentVariant.objects.exclude(all_content)
    if invalid_models.exists():
        print("Invalid content, please update or remove them:",
              ["{}:{}".format(t.code, t.name) for t in invalid_models])


class BaseContent(models.Model):
    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)

    # iterable or callable with (unique name, ctype) tuples
    # max name length is 20 chars.

    # use case: addons for usercontent, e.g. dependencies on external libraries
    # use case: model with different abilities
    appearances = None

    id = models.BigAutoField(primary_key=True, editable=False)
    # every content can specify its own deletion period
    deletion_period = getattr(settings, "DELETION_PERIOD_CONTENTS", None)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated_rel = GenericRelation("spider_base.AssignedContent")
    _associated2 = None

    _content_is_cleaned = False

    @property
    def associated(self):
        if self._associated2:
            return self._associated2
        return self.associated_rel.first()

    # if static_create is used and class not saved yet
    kwargs = None

    class Meta:
        abstract = True
        default_permissions = []

    @classmethod
    def static_create(cls, associated=None, **kwargs):
        ob = cls()
        if associated:
            ob._associated2 = associated
        ob.kwargs = kwargs
        ob.kwargs["parent_form"] = ob.kwargs.pop("form")
        return ob

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", name)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        else:
            return "%s: %s" % (
                self.localize_name(self.associated.ctype.name),
                self.id
            )

    def __repr__(self):
        return "<Content: %s>" % self.__str__()

    def get_instance_form(self, context):
        return self

    def get_form_kwargs(
        self, request, instance=None, disable_data=False, **kwargs
    ):
        """Return the keyword arguments for instantiating the form."""
        fkwargs = {}
        if instance is None:
            fkwargs["instance"] = self.get_instance_form(kwargs)
        elif instance:
            fkwargs["instance"] = instance

        if not disable_data and request.method in ('POST', 'PUT'):
            fkwargs.update({
                'data': request.POST,
                'files': request.FILES,
            })
        return fkwargs

    def get_form(self, scope):
        raise NotImplementedError

    def render_form(self, scope, **kwargs):
        parent_form = kwargs.get("form", None)
        kwargs["form"] = self.get_form(scope)(
            **self.get_form_kwargs(
                scope=scope,
                **kwargs
            )
        )
        if kwargs["form"].is_valid():
            kwargs["form"] = self.get_form(scope)(
                **self.get_form_kwargs(
                    scope=scope,
                    instance=kwargs["form"].save(),
                    **kwargs
                )
            )
        else:
            if parent_form and len(kwargs["form"].errors) > 0:
                parent_form.errors.setdefault(NON_FIELD_ERRORS, []).extend(
                    kwargs["form"].errors.setdefault(NON_FIELD_ERRORS, [])
                )
        template_name = "spider_base/base_form.html"
        return render_to_string(
            template_name, request=kwargs["request"],
            context=kwargs
        )

    @classmethod
    def create_from_import(cls, data):
        raise NotImplementedError

    def render_add(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            _("Add \"%s\"") % self.__str__()
        )
        kwargs.setdefault("confirm", _("Create"))
        return self.render_form(**kwargs)

    def render_update(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            _("Update \"%s\"") % self.__str__()
        )
        kwargs.setdefault("confirm", _("Update"))
        return self.render_form(**kwargs)

    def extract_form(
        self, context, datadic, zipf=None, level=1, prefix="", form=None,
        _was_embed=False
    ):
        if level <= 0:
            return
        if not form:
            form = self.get_form(context["scope"])(
                **self.get_form_kwargs(disable_data=True, **context)
            )
        AssignedContent = django_apps.get_model(
            "spider_base", "AssignedContent"
        )
        for name, field in form.fields.items():
            raw_value = form.initial[name]
            value = field.to_python(raw_value)
            if isinstance(value, AssignedContent):
                _level = level-1
                if (
                        hasattr(form.fields[name], "embed_content") and
                        not _was_embed and
                        # dereferencing would break stuff
                        context["scope"] != "export"
                   ):
                    _level += 1
                    _was_embed = True
                if _level > 0:
                    form2 = value.get_form(context["scope"])(
                        **value.get_form_kwargs(
                            disable_data=True, **context
                        )
                    )
                    pref = "{}{}/".format(prefix, name)
                    datadic[name] = OrderedDict(
                        pk=self.associated.pk,
                        ctype=self.associated.ctype.name
                    )
                    self.extract_form(
                        context, datadic[name], prefix=pref,
                        zipf=zipf, level=_level, form=form2,
                        _was_embed=_was_embed
                    )
                else:
                    datadic[name] = {
                        "pk": value.pk,
                        "ctype": value.ctype.name,
                        "info": value.info
                    }

            elif isinstance(value, File):
                path = "{}{}/{}".format(
                    prefix, name, os.path.basename(value.name)
                )
                if zipf:
                    zipf.write(value.path, path)
                datadic[name] = {"file": path}
            else:
                datadic[name] = raw_value

    def render_serialize(self, **kwargs):
        deref_level = 1
        if kwargs["request"].GET.get("deref", "") == "true":
            deref_level = 2
        llist = OrderedDict(
            pk=self.associated.pk,
            ctype=self.associated.ctype.name
        )
        if (
                kwargs["scope"] == "export" or
                kwargs["request"].GET.get("raw", "") == "embed"
           ):
            fil = tempfile.SpooledTemporaryFile(max_size=2048)
            with zipfile.ZipFile(fil, "w") as zip:
                self.extract_form(
                    kwargs, llist, zip,
                    level=deref_level
                )
                zip.writestr("data.json", json.dumps(llist))
            fil.seek(0, 0)
            ret = FileResponse(
                fil,
                content_type='application/force-download',
            )
            ret['Content-Disposition'] = 'attachment; filename=result.zip'
            return ret
        self.extract_form(
            kwargs, llist, level=deref_level
        )
        return JsonResponse(llist)

    def render_view(self, **kwargs):
        kwargs["form"] = self.get_form("view")(
            **self.get_form_kwargs(**kwargs)
        )
        if "raw" in kwargs["request"].GET:
            k = kwargs.copy()
            k["scope"] = "raw"
            return self.render_serialize(**k)
        kwargs.setdefault("no_button", True)
        template_name = "spider_base/full_form.html"
        return render_to_string(
            template_name, request=kwargs["request"],
            context=kwargs
        )

    def render(self, **kwargs):
        if kwargs["scope"] == "add":
            return self.render_add(**kwargs)
        elif kwargs["scope"] == "update":
            return self.render_update(**kwargs)
        elif kwargs["scope"] == "export":
            return self.render_serialize(**kwargs)
        else:
            return self.render_view(**kwargs)

    def get_info(self, no_public=False, unique=False):
        # no_public=False, unique=False shortcuts for get_info overwrites
        # passing down these parameters not neccessary
        no_public_var = ""
        if (
            no_public or
            UserContentType.public.value not in self.associated.ctype.ctype
           ):
            no_public_var = "no_public\n"
        if not unique:
            unique = (
                UserContentType.unique.value in self.associated.ctype.ctype
            )
        if unique:
            return "\ncode=%s\ntype=%s\n%sprimary\n" % \
                (
                    self._meta.model_name,
                    self.associated.ctype.name,
                    no_public_var
                )
        else:
            # simulates beeing not unique, by adding id
            # id is from this model, because assigned maybe not ready
            return "\ncode=%s\ntype=%s\n%sid=%s\n" % \
                (
                    self._meta.model_name,
                    self.associated.ctype.name,
                    no_public_var,
                    self.id if self.id else "None"  # placeholder
                )

    def full_clean(self, **kwargs):
        # checked with clean
        kwargs.setdefault("exclude", []).append("associated_rel")
        return super().full_clean(**kwargs)

    def clean(self):
        if self._associated2:
            self._associated2.content = self
        a = self.associated
        a.info = self.get_info()
        a.full_clean(exclude=["content"])
        self._content_is_cleaned = True

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)
        a = self.associated
        if settings.DEBUG:
            assert self._content_is_cleaned, "Uncleaned content committed"
        if self._associated2:
            a.content = self
            # add id to info
            if "\nunique\n" not in a.info:
                a.info = a.info.replace(
                    "\nid=None\n", "\nid={}\n".format(self.id), 1
                )
        # update info and set content
        a.save()
        # require again cleaning
        self._content_is_cleaned = False
        return ret
