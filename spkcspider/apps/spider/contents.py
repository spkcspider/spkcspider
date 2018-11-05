
__all__ = (
    "add_content", "installed_contents", "BaseContent"
)
import logging
from urllib.parse import urljoin
from django.apps import apps as django_apps
from django.db import models
from django.utils.translation import gettext
from django.template.loader import render_to_string
from django.core.files.base import File

from django.contrib.contenttypes.fields import GenericRelation
from django.http import HttpResponse
from django.conf import settings
from django.utils.translation import pgettext

from rdflib import Literal, Graph, BNode, URIRef
from rdflib.namespace import XSD

from .constants import UserContentType, spkcgraph
from .serializing import paginated_contents, serialize_stream
from .helpers import merge_get_url, get_settings_func, add_property


installed_contents = {}

# don't spam set objects
_empty_set = set()

# never use these names
forbidden_names = ["Content", "UserComponent"]

# updated attributes of ContentVariant
_attribute_list = ["name", "ctype", "strength"]


def add_content(klass):
    code = klass._meta.model_name
    if code in installed_contents:
        raise Exception("Duplicate content")
    if "{}.{}".format(klass.__module__, klass.__qualname__) not in getattr(
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
            assert dic["name"] not in forbidden_names, \
                "Forbidden content name: %" % dic["name"]
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

    hashed_fields = None

    id = models.BigAutoField(primary_key=True, editable=False)
    # every content can specify its own deletion period
    deletion_period = getattr(settings, "DELETION_PERIOD_CONTENTS", None)
    # if created associated is None (will be set later)
    # use usercomponent in form instead
    associated_rel = GenericRelation("spider_base.AssignedContent")
    _associated_tmp = None

    _content_is_cleaned = False

    @property
    def associated(self):
        if self._associated_tmp:
            return self._associated_tmp
        return self.associated_rel.filter(fake_id__isnull=True).first()

    # if static_create is used and class not saved yet
    kwargs = None

    class Meta:
        abstract = True
        default_permissions = []

    @classmethod
    def static_create(cls, associated=None, **kwargs):
        ob = cls()
        if associated:
            ob._associated_tmp = associated
        ob.kwargs = kwargs
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

    def get_size(self):
        return 0

    def get_strength(self):
        """ get required strength """
        return self.associated.ctype.strength

    def get_strength_link(self):
        """ get required strength for links """
        return self.get_strength()

    def get_protected_preview(self):
        """
            description shown for spider if public and protections are active
        """
        return ""

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

    # default scopes:
    #  public accessible:
    #   raw: view with raw parameter
    #   list: raw but embedded in content list
    #   view: view of conten without raw parameter
    #  only accessible by owner and staff:
    #   add: create view of content
    #   update: update view of content
    #   raw_update: special update mode for machines or really fancy updates
    #   export: like raw just optimized for export: e.g. no dereferencing
    def get_form(self, scope):
        raise NotImplementedError

    def get_template_name(self, scope):
        if scope in ["add", "update"]:
            return 'spider_base/base_form.html'
        return 'spider_base/view_form.html'

    def render_form(self, scope, **kwargs):
        _ = gettext
        if scope == "add":
            kwargs["form_empty_message"] = _("<b>No User Input required</b>")
            size_diff = 0
        else:
            size_diff = self.get_size()
        parent_form = kwargs.get("form", None)
        kwargs["form"] = self.get_form(scope)(
            **self.get_form_kwargs(
                scope=scope,
                **kwargs
            )
        )
        if kwargs["form"].is_valid():
            instance = kwargs["form"].save(False)
            size_diff = kwargs["form"].instance.get_size() - size_diff
            if size_diff != 0:
                ret = self.associated.usercomponent.user_info.update_quota(
                    size_diff
                )
                if ret:
                    kwargs["form"].add_error(None, ret)
        if kwargs["form"].is_valid():
            kwargs["form"] = self.get_form(scope)(
                **self.get_form_kwargs(
                    scope=scope,
                    instance=instance.save(),
                    **kwargs
                )
            )

        else:
            if parent_form and len(kwargs["form"].errors) > 0:
                parent_form.add_error(None, kwargs["form"].errors)
        return (
            render_to_string(
                self.get_template_name(scope),
                request=kwargs["request"], context=kwargs
            ),
            kwargs["form"].media
        )

    def get_absolute_url(self):
        return self.associated.get_absolute_url()

    def get_references(self):
        return []

    def map_data(self, name, data, context):
        from .models import AssignedContent
        if isinstance(data, AssignedContent):
            url = merge_get_url(
                urljoin(
                    context["hostpart"],
                    data.get_absolute_url()
                ),
                raw=context["request"].GET["raw"]
            )
            return (
                "url",
                Literal(
                    url,
                    datatype=XSD.anyURI,
                )
            )
        elif isinstance(data, File):
            return get_settings_func(
                "SPIDER_FILE_EMBED_FUNC",
                "spkcspider.apps.spider.functions.embed_file_default"
            )(name, data, self, context)
        return (
            "value",
            Literal(data)
        )

    def transform_field(self, name, form, context):
        if self.hashed_fields and name in self.hashed_fields:
            return name, True
        else:
            return name, False

    def serialize(self, graph, content_ref, context):
        form = self.get_form(context["scope"])(
            **self.get_form_kwargs(
                disable_data=True,
                **context
            )
        )
        graph.add((
            content_ref,
            spkcgraph["type"],
            Literal(self.associated.getlist("type", 1)[0])
        ))

        for name, field in form.fields.items():
            raw_value = form.initial.get(name, None)
            try:
                value = field.to_python(raw_value)
            except Exception as exc:
                # user can corrupt tags, so just debug
                level = logging.WARNING
                if getattr(form, "layout_generating_form", False):
                    level = logging.DEBUG
                logging.log(
                    level,
                    "Corrupted field: %s, form: %s, error: %s",
                    name, form, exc
                )
                continue
            value_node = BNode()
            newname, hashable = self.transform_field(name, form, context)

            graph.add((
                content_ref,
                spkcgraph["property"],
                value_node
            ))
            graph.add((
                value_node,
                spkcgraph["hashable"],
                Literal(hashable)
            ))
            graph.add((
                value_node,
                spkcgraph["name"],
                Literal(newname)
            ))
            graph.add((
                value_node,
                spkcgraph["fieldname"],
                Literal(name)
            ))

            if not isinstance(value, (list, tuple, models.QuerySet)):
                value = [value]

            for i in value:
                type_, encoded = self.map_data(name, i, context)
                graph.add((
                    value_node,
                    spkcgraph[type_],
                    encoded
                ))

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

    def render_serialize(self, **kwargs):
        from .models import AssignedContent
        # ** creates copy of dict, so it is safe to overwrite kwargs here

        session_dict = {
            "request": kwargs["request"],
            "context": kwargs,
            "scope": kwargs["scope"],
            "hostpart": kwargs["hostpart"],
            "ac_namespace": spkcgraph["content"],
            "sourceref": URIRef(kwargs["hostpart"] + kwargs["request"].path)
        }

        g = Graph()

        p = paginated_contents(
            AssignedContent.objects.filter(id=self.associated.id),
            getattr(settings, "SERIALIZED_PER_PAGE", 50)
        )
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass
        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=True
        )
        if hasattr(kwargs["request"], "token_expires"):
            session_dict["expires"] = kwargs["request"].token_expires.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )
            if page <= 1:
                add_property(
                    g, "token_expires", ob=session_dict["request"],
                    ref=session_dict["sourceref"]
                )
        if page <= 1:
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(kwargs["scope"])
            ))

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )

        if session_dict.get("expires", None):
            ret['X-Token-Expires'] = session_dict["expires"]
        return ret

    def render_view(self, **kwargs):
        if "raw" in kwargs["request"].GET:
            k = kwargs.copy()
            k["scope"] = "raw"
            return self.render_serialize(**k)

        kwargs["form"] = self.get_form("view")(
            **self.get_form_kwargs(disable_data=True, **kwargs)
        )
        kwargs.setdefault("namespace_form", "content")
        kwargs.setdefault(
            "namespace_sub",
            "{}/".format(self.associated.getlist("type", 1)[0])
        )
        return (
            render_to_string(
                self.get_template_name(kwargs["scope"]),
                request=kwargs["request"],
                context=kwargs
            ),
            kwargs["form"].media
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
            assignedid = "None"  # placeholder
            if getattr(self.associated, "id", None):
                assignedid = self.associated.id
            return "\ncode=%s\ntype=%s\nid=%s\n" % \
                (
                    self._meta.model_name,
                    self.associated.ctype.name,
                    assignedid
                )

    def full_clean(self, **kwargs):
        # checked with clean
        kwargs.setdefault("exclude", []).append("associated_rel")
        return super().full_clean(**kwargs)

    def clean(self):
        if self._associated_tmp:
            self._associated_tmp.content = self
        a = self.associated
        a.info = self.get_info()
        a.strength = self.get_strength()
        a.strength_link = self.get_strength_link()
        a.full_clean(exclude=["content"])
        # persist AssignedContent for saving
        self._associated_tmp = a
        self._content_is_cleaned = True

    def save(self, *args, **kwargs):
        if settings.DEBUG:
            assert self._content_is_cleaned, "try to save uncleaned content"
        super().save(*args, **kwargs)
        a = self.associated
        if settings.DEBUG:
            assert a.content, "associated lacks \"self\" as content"
        update_id = False
        if not getattr(a, "id", None):
            update_id = True
        # update info and set content
        a.save()
        if update_id:
            # add id to info
            if "\nprimary\n" not in a.info:
                a.info = a.info.replace(
                    "\nid=None\n", "\nid={}\n".format(a.id), 1
                )
                # second save required
                a.save()
        # needs id first
        a.references.set(self.get_references())
        # update fakes
        fakes = self.associated_rel.filter(fake_id__isnull=False)
        fakes.update(
            info=a.info, strength=a.strength, strength_link=a.strength_link,
            nonce=a.nonce
        )
        # update references of fakes
        for i in fakes:
            i.references.set(a.references)
        # require cleaning again
        self._content_is_cleaned = False
