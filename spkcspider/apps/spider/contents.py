
__all__ = (
    "add_content", "installed_contents", "BaseContent"
)
import json
from collections import OrderedDict

from django.apps import apps as django_apps
from django.db import models
from django.utils.translation import gettext
from django.core.exceptions import NON_FIELD_ERRORS
from django.template.loader import render_to_string
from django.core.files.base import File

from django.contrib.contenttypes.fields import GenericRelation
from django.http import JsonResponse
from django.conf import settings
from django.utils.translation import pgettext

from .constants import UserContentType
from .helpers import get_settings_func


installed_contents = {}

# don't spam set objects
_empty_set = set()

# updated attributes of ContentVariant
_attribute_list = ["name", "ctype", "strength"]


def add_content(klass):
    code = klass._meta.model_name
    if code in installed_contents:
        raise Exception("Duplicate content")
    if klass.__qualname__ not in getattr(
        settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
    ):
        installed_contents[code] = klass
    return klass


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
        for dic in appearances:
            if update:
                variant = ContentVariant.objects.get_or_create(
                    defaults=dic, code=code
                )[0]
            else:
                variant = ContentVariant.objects.get_or_create(
                    defaults=dic, code=code, name=dic["name"]
                )[0]
            require_save = False
            for key in _attribute_list:
                val = dic.get(
                    key, variant._meta.get_field(key).get_default()
                )
                if getattr(variant, key) != val:
                    setattr(variant, key, val)
                    require_save = True
            if require_save:
                variant.save()
            all_content |= models.Q(name=dic["name"], code=code)
    invalid_models = ContentVariant.objects.exclude(all_content)
    if invalid_models.exists():
        print("Invalid content, please update or remove them:",
              ["{}:{}".format(t.code, t.name) for t in invalid_models])


class BaseContent(models.Model):
    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)

    # iterable or callable returning iterable containing dicts
    # required keys: name
    # optional: strength (default=0), ctype (default="")
    # max name length is 50 chars
    # max ctype length is 10 chars (10 attributes)

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

    def get_strength(self):
        """ get required strength """
        return self.associated.ctype.strength

    def get_strength_link(self):
        """ get required strength for links """
        return self.get_strength()

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

    def get_template_name(self, scope):
        if scope in ["add", "update"]:
            'spider_base/base_form.html'
        return 'spider_base/full_form.html'

    def render_form(self, scope, **kwargs):
        _ = gettext
        if scope == "add":
            kwargs["form_empty_message"] = _("<b>No User Input required</b>")
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
        return render_to_string(
            self.get_template_name(kwargs["scope"]),
            request=kwargs["request"], context=kwargs
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
        self, context, datadic, zipf=None, level=1, prefix="", form=None
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
            raw_value = form.initial.get(name, None)
            value = field.to_python(raw_value)
            if isinstance(value, AssignedContent):
                _level = level-1
                if (
                        getattr(field, "force_embed", False) and
                        # dereferencing would break stuff
                        context["scope"] != "export"
                   ):
                    _level += 1
                if _level > 0:
                    context["uc"] = value.associated.usercomponent
                    form2 = value.get_form(context["scope"])(
                        **value.get_form_kwargs(
                            disable_data=True, **context
                        )
                    )
                    pref = "{}{}/".format(prefix, name)
                    datadic[name] = OrderedDict(
                        pk=self.associated.pk,
                        ctype=self.associated.ctype.name,
                        info=self.associated.info
                    )
                    self.extract_form(
                        context, datadic[name], prefix=pref,
                        zipf=zipf, level=_level, form=form2,
                    )
                else:
                    datadic[name] = {
                        "pk": value.pk,
                        "ctype": value.ctype.name,
                        "info": value.info
                    }

            elif isinstance(value, File):
                datadic[name] = get_settings_func(
                    "EMBED_FILE_FUNC",
                    "spkcspider.apps.spider.functions.embed_file_default"
                )(
                    prefix=prefix, name=name, value=value,
                    zipf=zipf, context=context
                )
            else:
                datadic[name] = raw_value

    def generate_embedded(self, zip, context):
        store_dict = context["store_dict"]
        context["content"] = self
        deref_level = 2
        if store_dict["scope"] == "export":
            deref_level = 1
        self.extract_form(
            context, store_dict, zip, level=deref_level
        )
        zip.writestr(
            "data.json", json.dumps(store_dict)
        )

    def render_serialize(self, **kwargs):
        # ** creates copy of dict, so it is safe to overwrite kwargs here

        session_dict = {
            "request": kwargs["request"],
            "context": kwargs,
            "scope": kwargs["scope"],
            "hostpart": kwargs["hostpart"]
        }
        store_dict = OrderedDict(
            pk=self.associated.pk,
            ctype=self.associated.ctype.name,
            modified=self.associated.modified.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            ),
            scope=kwargs["scope"],
            info=self.associated.info,
            expires=None  # replaced with expire date of token
        )
        session_dict["store_dict"] = store_dict
        if hasattr(kwargs["request"], "token_expires"):
            store_dict["expires"] = kwargs["request"].token_expires.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )
            session_dict["expires"] = store_dict["expires"]
        if (
                kwargs["scope"] == "export" or
                kwargs["request"].GET.get("raw", "") == "embed"
           ):
            return get_settings_func(
                "GENERATE_EMBEDDED_FUNC",
                "spkcspider.apps.spider.functions.generate_embedded"
            )(self.generate_embedded, session_dict, self.associated)

        self.extract_form(kwargs, store_dict, level=2)
        ret = JsonResponse(store_dict)
        if store_dict["expires"]:
            ret['X-Token-Expires'] = store_dict["expires"]
        return ret

    def render_view(self, **kwargs):
        if "raw" in kwargs["request"].GET:
            k = kwargs.copy()
            k["scope"] = "raw"
            return self.render_serialize(**k)

        kwargs["form"] = self.get_form("view")(
            **self.get_form_kwargs(disable_data=True, **kwargs)
        )
        kwargs.setdefault("no_button", True)
        return render_to_string(
            self.get_template_name(kwargs["scope"]), request=kwargs["request"],
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

    def get_info(self, unique=False):
        # unique=False shortcuts for get_info overwrites
        # passing down these parameters not neccessary
        if not unique:
            unique = (
                UserContentType.unique.value in self.associated.ctype.ctype
            )
        if unique:
            return "\ncode=%s\ntype=%s\nprimary\n" % \
                (
                    self._meta.model_name,
                    self.associated.ctype.name,
                )
        else:
            # simulates beeing not unique, by adding id
            # id is from this model, because assigned maybe not ready
            return "\ncode=%s\ntype=%s\nid=%s\n" % \
                (
                    self._meta.model_name,
                    self.associated.ctype.name,
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
        a.strength = self.get_strength()
        a.strength_link = self.get_strength_link()
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
            if "\nprimary\n" not in a.info:
                a.info = a.info.replace(
                    "\nid=None\n", "\nid={}\n".format(self.id), 1
                )
        # update info and set content
        a.save()
        # require again cleaning
        self._content_is_cleaned = False
        return ret
