
__all__ = (
    "add_content", "installed_contents", "BaseContent"
)
import logging
from urllib.parse import urljoin
from functools import lru_cache

from django.apps import apps as django_apps
from django.db import models, transaction
from django.utils.translation import gettext
from django.template.loader import render_to_string
from django.core.files.base import File
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.http import Http404
from django.db.utils import IntegrityError
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.contenttypes.fields import GenericRelation
from django.http.response import HttpResponseBase, HttpResponse
from django.conf import settings
from django.utils.translation import pgettext
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from rdflib import Literal, Graph, BNode, URIRef, XSD

from .constants import VariantType, spkcgraph, ActionUrl, SPIDER_ANCHOR_DOMAIN
from .serializing import paginate_stream, serialize_stream
from .helpers import (
    get_settings_func, add_property, create_b64_id_token
)
from .templatetags.spider_rdf import literalize

installed_contents = {}

# don't spam set objects
_empty_set = frozenset()

default_abilities = frozenset(
    ("add", "view", "update", "export", "list", "raw", "raw_update")
)

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
            require_save = False
            assert dic["name"] not in forbidden_names, \
                "Forbidden content name: %" % dic["name"]
            try:
                with transaction.atomic():
                    if update:
                        variant = ContentVariant.objects.get_or_create(
                            defaults=dic, code=code
                        )[0]
                    else:
                        variant = ContentVariant.objects.get_or_create(
                            defaults=dic, code=code, name=dic["name"]
                        )[0]

            except IntegrityError:
                # renamed model = code changed
                variant = ContentVariant.objects.get(name=dic["name"])
                variant.code = code
                require_save = True

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
              ["\"{}\":{}".format(t.code, t.name) for t in invalid_models])


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
    deletion_period = getattr(
        settings, "SPIDER_CONTENTS_DEFAULT_DELETION_PERIOD", None
    )
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

    class Meta:
        abstract = True
        default_permissions = []

    @classmethod
    def static_create(cls, *, associated=None):
        ob = cls()
        if associated:
            ob._associated_tmp = associated
        return ob

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", name)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        else:
            return "%s:%s" % (
                self.localize_name(self.associated.ctype.name),
                self.associated.id
            )

    def __repr__(self):
        return "<Content: %s>" % self.__str__()

    def get_size(self):
        return 0

    def get_priority(self):
        return 0

    @classmethod
    def feature_urls(cls):
        """ For implementing component features """
        return []

    @classmethod
    @lru_cache(typed=True)
    def cached_feature_urls(cls):
        return list(map(
            lambda x: ActionUrl(*x),
            cls.feature_urls()
        ))

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

    def get_abilities(self, context):
        """ Override for declaring content extra abilities """
        return set()

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

    def update_used_space(self, size_diff):
        if size_diff == 0:
            return
        f = "local"
        if VariantType.component_feature.value in self.associated.ctype.ctype:
            f = "remote"
        with transaction.atomic():
            self.associated.usercomponent.user_info.update_with_quota(
                    size_diff, f
                )
            self.associated.usercomponent.user_info.save(
                update_fields=[
                    "used_space_local", "used_space_remote"
                ]
            )

    def render_form(self, scope, **kwargs):
        _ = gettext
        if scope == "add":
            kwargs["form_empty_message"] = _("<b>No User Input required</b>")
            old_size = 0
        else:
            old_size = self.get_size()
        parent_form = kwargs.get("form", None)
        kwargs["form"] = self.get_form(scope)(
            **self.get_form_kwargs(
                scope=scope,
                **kwargs
            )
        )
        if kwargs["form"].is_valid():
            instance = kwargs["form"].save(False)
            try:
                self.update_used_space(
                    instance.get_size() - old_size
                )
            except ValidationError as exc:
                kwargs["form"].add_error(None, exc)
                messages.error(
                    kwargs["request"], _('Space exhausted')
                )
        if kwargs["form"].is_valid():
            instance.save()
            kwargs["form"].save_m2m()
            messages.success(
                kwargs["request"], _('Content updated')
            )
            kwargs["form"] = self.get_form(scope)(
                **self.get_form_kwargs(
                    scope=scope,
                    instance=instance,
                    **kwargs
                )
            )

        else:
            if (
                parent_form and
                len(kwargs["form"].errors.get(NON_FIELD_ERRORS, [])) > 0
            ):
                parent_form.add_error(
                    None, kwargs["form"].errors[NON_FIELD_ERRORS]
                )
        return (
            render_to_string(
                self.get_template_name(scope),
                request=kwargs["request"], context=kwargs
            ),
            kwargs["form"].media
        )

    def get_absolute_url(self, scope="view"):
        return self.associated.get_absolute_url(scope)

    def get_primary_anchor(self, graph, context):
        p = self.associated.usercomponent.primary_anchor
        if p:
            return urljoin(
                SPIDER_ANCHOR_DOMAIN,
                p.get_absolute_url()
            )

        if not p and self.associated.usercomponent.public:
            return urljoin(
                SPIDER_ANCHOR_DOMAIN,
                self.associated.usercomponent.get_absolute_url()
            )
        return urljoin(
            SPIDER_ANCHOR_DOMAIN, context["request"].path
        )

    def get_references(self):
        return []

    def map_data(self, name, field, data, graph, context):
        if isinstance(data, File):
            return get_settings_func(
                "SPIDER_FILE_EMBED_FUNC",
                "spkcspider.apps.spider.functions.embed_file_default"
            )(name, data, self, context)
        return literalize(data, field)

    def serialize(self, graph, ref_content, context):
        form = self.get_form(context["scope"])(
            **self.get_form_kwargs(
                disable_data=True,
                **context
            )
        )
        graph.add((
            ref_content,
            spkcgraph["type"],
            Literal(self.associated.getlist("type", 1)[0])
        ))
        if "abilities" not in context:
            context["abilities"] = set(self.get_abilities(context))

        for ability in context["abilities"]:
            assert(ability not in default_abilities)

            graph.add((
                ref_content,
                spkcgraph["ability:name"],
                Literal(ability, datatype=XSD.string)
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
            hashable = getattr(field, "hashable", False)

            graph.add((
                ref_content,
                spkcgraph["properties"],
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
                Literal(name, datatype=XSD.string)
            ))
            graph.add((
                value_node,
                spkcgraph["fieldname"],
                Literal(form.add_prefix(name), datatype=XSD.string)
            ))

            if not isinstance(value, (list, tuple, models.QuerySet)):
                value = [value]

            for i in value:
                graph.add((
                    value_node,
                    spkcgraph["value"],
                    self.map_data(name, field, i, graph, context)
                ))

    def render_serialize(self, **kwargs):
        from .models import AssignedContent
        # ** creates copy of dict, so it is safe to overwrite kwargs here

        session_dict = {
            "request": kwargs["request"],
            "context": kwargs,
            "scope": kwargs["scope"],
            "hostpart": kwargs["hostpart"],
            "ac_namespace": spkcgraph["contents"],
            "sourceref": URIRef(urljoin(
                kwargs["hostpart"], kwargs["request"].path
            ))
        }

        g = Graph()
        g.namespace_manager.bind("spkc", spkcgraph, replace=True)

        p = paginate_stream(
            AssignedContent.objects.filter(id=self.associated.id),
            getattr(settings, "SERIALIZED_PER_PAGE", 50),
            getattr(settings, "SERIALIZED_MAX_DEPTH", 20)
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
                Literal(kwargs["scope"], datatype=XSD.string)
            ))

            uc = kwargs.get("source", self.associated.usercomponent)
            g.add((
                session_dict["sourceref"], spkcgraph["strength"],
                Literal(uc.strength)
            ))
            if kwargs["referrer"]:
                g.add((
                    session_dict["sourceref"],
                    spkcgraph["referrer"],
                    Literal(kwargs["referrer"], datatype=XSD.anyURI)
                ))
            if kwargs["token_strength"]:
                add_property(
                    g, "token_strength", ref=session_dict["sourceref"],
                    literal=kwargs["token_strength"]
                )
            add_property(
                g, "intentions", ref=session_dict["sourceref"],
                literal=kwargs["intentions"], datatype=XSD.string,
                iterate=True
            )

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )

        if session_dict.get("expires", None):
            ret['X-Token-Expires'] = session_dict["expires"]
        # allow cors requests for raw
        ret["Access-Control-Allow-Origin"] = "*"
        return ret

    def access_view(self, **kwargs):
        _ = gettext

        kwargs["form"] = self.get_form("view")(
            **self.get_form_kwargs(disable_data=True, **kwargs)
        )
        kwargs.setdefault("legend", _("View"))
        # not required: done by access template
        # kwargs.setdefault(
        #    "add_spkc_types",
        #    [
        #        self.associated.getlist("type", 1)[0],
        #        "Content"
        #    ]
        # )
        return (
            render_to_string(
                self.get_template_name(kwargs["scope"]),
                request=kwargs["request"],
                context=kwargs
            ),
            kwargs["form"].media
        )

    def access_add(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            _("Add \"%s\"") % self.__str__()
        )
        # not visible by default
        kwargs.setdefault("confirm", _("Create"))
        # prevent second button
        kwargs.setdefault("inner_form", True)
        return self.render_form(**kwargs)

    def access_update(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            _("Update \"%s\"") % self.__str__()
        )
        # not visible by default
        kwargs.setdefault("confirm", _("Update"))
        # prevent second button
        kwargs.setdefault("inner_form", True)
        return self.render_form(**kwargs)

    def access_export(self, **kwargs):
        kwargs["scope"] = "export"
        return self.render_serialize(**kwargs)

    def access_raw(self, **kwargs):
        kwargs["scope"] = "raw"
        return self.render_serialize(**kwargs)

    @csrf_exempt
    def access_default(self, **kwargs):
        raise Http404()

    access_raw_update = access_default

    def access(self, context):
        # context is updated and used outside!!
        # so make sure that func gets only a copy (**)
        context["abilities"] = set(self.get_abilities(context))
        context.setdefault("extra_outer_forms", [])
        func = self.access_default
        if context["scope"] == "view" and "raw" in context["request"].GET:
            func = self.access_raw
        elif context["scope"] in default_abilities:
            func = getattr(self, "access_{}".format(context["scope"]))
        elif context["scope"] in context["abilities"]:
            func = getattr(self, "access_{}".format(context["scope"]))

        # check csrf tokens manually
        if not getattr(func, "csrf_exempt", False):
            csrferror = CsrfViewMiddleware().process_view(
                context["request"], None, (), {}
            )
            if csrferror is not None:
                # csrferror is HttpResponse
                return csrferror
        ret = func(**context)
        if context["scope"] == "update":
            # update function should never return HttpResponse
            #  (except csrf error)
            assert(not isinstance(ret, HttpResponseBase))
        return ret

    def get_info(self, unique=None, unlisted=None):
        # unique=None, feature=None shortcuts for get_info overwrites
        # passing down these parameters not neccessary
        if unique is None:
            unique = (
                VariantType.unique.value in self.associated.ctype.ctype
            )
        if unlisted is None:
            unlisted = (
                VariantType.component_feature.value in
                self.associated.ctype.ctype or
                VariantType.content_feature.value in
                self.associated.ctype.ctype
            )

        anchortag = ""
        if VariantType.anchor.value in self.associated.ctype.ctype:
            anchortag = "anchor\n"

        idtag = "primary\n"
        # simulates beeing not unique, by adding id
        if not unique:
            idtag = "id=None\n"  # placeholder
            if getattr(self.associated, "id", None):
                idtag = "id={}\n".format(self.associated.id)
        unlistedtag = ""
        if unlisted:
            unlistedtag = "unlisted\n"
        return "\nmodel={}.{}\ntype={}\n{}{}{}".format(
            self._meta.label,
            self._meta.model_name,
            self.associated.ctype.name,
            idtag,
            anchortag,
            unlistedtag
        )

    def full_clean(self, **kwargs):
        # checked with clean
        kwargs.setdefault("exclude", []).append("associated_rel")
        return super().full_clean(**kwargs)

    def clean(self):
        if self._associated_tmp:
            self._associated_tmp.content = self
        assignedcontent = self.associated
        assignedcontent.info = self.get_info()
        assignedcontent.priority = self.get_priority()
        assignedcontent.strength = self.get_strength()
        assignedcontent.strength_link = self.get_strength_link()
        assignedcontent.full_clean(exclude=["content"])
        # persist AssignedContent for saving
        self._associated_tmp = assignedcontent
        self._content_is_cleaned = True

    def save(self, *args, **kwargs):
        if settings.DEBUG:
            assert self._content_is_cleaned, "try to save uncleaned content"
        super().save(*args, **kwargs)
        assignedcontent = self.associated
        if not assignedcontent.content:
            # add requires this
            assignedcontent.content = self
            assignedcontent.info = self.get_info()
            assignedcontent.strength = self.get_strength()
            assignedcontent.strength_link = self.get_strength_link()
        created = False
        if not getattr(assignedcontent, "id", None):
            created = True
        # update info and set content
        assignedcontent.save()
        if created:
            to_save = set()
            # add id to info
            if "\nprimary\n" not in assignedcontent.info:
                assignedcontent.info = assignedcontent.info.replace(
                    "\nid=None\n", "\nid={}\n".format(
                        assignedcontent.id
                    ), 1
                )
                to_save.add("info")
            if (
                assignedcontent.token_generate_new_size is not None and
                not assignedcontent.token
            ):
                assignedcontent.token_generate_new_size = \
                    getattr(settings, "TOKEN_SIZE", 30)
            # set token
            if assignedcontent.token_generate_new_size is not None:
                if assignedcontent.token:
                    print(
                        "Old nonce for Content id:", assignedcontent.id,
                        "is", assignedcontent.token
                    )
                assignedcontent.token = create_b64_id_token(
                    assignedcontent.id,
                    "/",
                    assignedcontent.token_generate_new_size
                )
                assignedcontent.token_generate_new_size = None
                to_save.add("token")
            # second save required
            if to_save:
                assignedcontent.save(update_fields=to_save)
        # needs id first
        s = set(assignedcontent.attached_contents.all())
        s.update(self.get_references())
        assignedcontent.references.set(s)
        # update fakes
        # fakes = self.associated_rel.filter(fake_id__isnull=False)
        # fakes.update(
        #     info=assignedcontent.info,
        #     strength=assignedcontent.strength,
        #     strength_link=assignedcontent.strength_link,
        #     nonce=assignedcontent.nonce
        # )
        # update references of fakes
        # for i in fakes:
        #     i.references.set(assignedcontent.references)
        # require cleaning again
        self._content_is_cleaned = False
