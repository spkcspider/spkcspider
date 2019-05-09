
__all__ = (
    "add_content", "installed_contents", "BaseContent"
)
import logging
from urllib.parse import urljoin
from functools import lru_cache

from django.utils.html import escape
from django.apps import apps as django_apps
from django.db import models, transaction
from django.utils.translation import gettext, pgettext
from django.template.loader import render_to_string
from django.core.files.base import File
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.http import Http404
from django.db.utils import IntegrityError
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.contenttypes.fields import GenericRelation
from django.http.response import HttpResponseBase, HttpResponse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from rdflib import Literal, Graph, BNode, URIRef, XSD

from .constants import VariantType, spkcgraph, ActionUrl
from .conf import get_anchor_domain
from .serializing import paginate_stream, serialize_stream
from .helpers import (
    get_settings_func, add_property, create_b64_id_token, merge_get_url
)
from .templatetags.spider_rdf import literalize

logger = logging.getLogger(__name__)

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
    valid_for = {}
    for code, val in installed_contents.items():
        appearances = val.appearances
        if callable(appearances):
            appearances = appearances()

        # update name if only one name exists
        update = False
        if len(appearances) == 1:
            update = True

        for attr_dict in appearances:
            require_save = False
            assert attr_dict["name"] not in forbidden_names, \
                "Forbidden content name: %" % attr_dict["name"]
            attr_dict = attr_dict.copy()
            _v_for = attr_dict.pop("valid_feature_for", None)
            try:
                with transaction.atomic():
                    if update:
                        variant = ContentVariant.objects.get_or_create(
                            defaults=attr_dict, code=code
                        )[0]
                    else:
                        variant = ContentVariant.objects.get_or_create(
                            defaults=attr_dict, code=code,
                            name=attr_dict["name"]
                        )[0]

            except IntegrityError:
                # renamed model = code changed
                variant = ContentVariant.objects.get(name=attr_dict["name"])
                variant.code = code
                require_save = True

            if _v_for:
                if _v_for == "*":
                    valid_for[attr_dict["name"]] = (variant, set("*"))
                else:
                    valid_for[attr_dict["name"]] = (variant, set(_v_for))
            elif VariantType.content_feature.value in variant.ctype:
                logger.warning(
                    "%s defines content_feature but defines no "
                    "\"valid_feature_for\"", variant.name
                )

            for key in _attribute_list:
                val = attr_dict.get(
                    key, variant._meta.get_field(key).get_default()
                )
                if getattr(variant, key) != val:
                    setattr(variant, key, val)
                    require_save = True
            if require_save:
                variant.save()
            all_content |= models.Q(name=attr_dict["name"], code=code)
    for val in valid_for.values():
        try:
            # try first to exclude by stripping "*" and checking error
            val[1].remove("*")
            val[0].valid_feature_for.set(ContentVariant.objects.exclude(
                name__in=val[1]
            ))
        except KeyError:
            val[0].valid_feature_for.set(ContentVariant.objects.filter(
                name__in=val[1]
            ))

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
    # conditional required: valid_feature_for
    # max name length is 50 chars
    # max ctype length is 10 chars (10 attributes)
    # valid_feature_for is  a list or if "*" also an string.
    #  "*" inverts choices so parameters are blacklisted instead whitelisted

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
    associated_rel = GenericRelation(
        "spider_base.AssignedContent",
        content_type_field='content_type', object_id_field='object_id'
    )
    associated_obj = None

    # user can set name
    # if set to "force" name will be enforced
    expose_name = True
    # user can set description
    expose_description = False
    # use if you want to force a token size
    force_token_size = None

    associated_errors = None

    _content_is_cleaned = False

    @property
    def associated(self):
        if self.associated_obj:
            return self.associated_obj
        return self.associated_rel.first()

    class Meta:
        abstract = True
        default_permissions = []

    @classmethod
    def static_create(
        cls, *, associated=None, associated_kwargs=None, content_kwargs=None,
        token_size=None
    ):
        if content_kwargs:
            ob = cls(**content_kwargs)
        else:
            ob = cls()
        if associated:
            ob.associated_obj = associated
        else:
            from .models import AssignedContent
            ob = cls()
            if not associated_kwargs:
                associated_kwargs = {}
            associated_kwargs["content"] = ob
            ob.associated_obj = AssignedContent(**associated_kwargs)
        if token_size is not None:
            ob.associated_obj.token_generate_new_size = token_size
        return ob

    @classmethod
    def localize_name(cls, name):
        return pgettext("content name", name)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        else:
            return self.associated.name

    def __repr__(self):
        return "<Content: ({}: {})>".format(
            self.associated.usercomponent.username, self.__str__()
        )

    def get_size(self):
        # 255 = length name no matter what encoding
        s = 255
        if self.expose_description and self.associated:
            s += len(self.associated.description)
        return s

    def get_priority(self):
        return 0

    @classmethod
    def feature_urls(cls, name):
        """ For implementing component features """
        return []

    @classmethod
    @lru_cache(typed=True)
    def cached_feature_urls(cls, name):
        return frozenset(map(
            lambda x: ActionUrl(*x),
            cls.feature_urls(name)
        ))

    def get_content_name(self):
        return "{}_{}".format(
            self.localize_name(self.associated.ctype.name),
            self.associated.id
        )

    def get_content_description(self):
        return " "

    def localized_description(self):
        """ localize and perform other transforms before rendering to user """
        if not self.expose_description:
            return self.associated.description
        return gettext(self.associated.description)

    def get_strength(self):
        """ get required strength """
        return self.associated.ctype.strength

    def get_strength_link(self):
        """ get required strength for links """
        return self.get_strength()

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
            return 'spider_base/partials/base_form.html'
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
                    disable_data=True,  # required for using object data
                    **kwargs
                )
            )

        elif parent_form:
            if len(kwargs["form"].errors.get(NON_FIELD_ERRORS, [])) > 0:
                parent_form.add_error(
                    None, kwargs["form"].errors.pop(NON_FIELD_ERRORS)
                )
            if self.associated_errors:
                parent_form.add_error(
                    None, self.associated_errors
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
                get_anchor_domain(),
                p.get_absolute_url()
            )

        if not p and self.associated.usercomponent.public:
            return urljoin(
                get_anchor_domain(),
                self.associated.usercomponent.get_absolute_url()
            )
        return urljoin(
            get_anchor_domain(), context["request"].path
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
                logger.log(
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
            getattr(
                settings, "SPIDER_SERIALIZED_PER_PAGE",
                settings.SPIDER_OBJECTS_PER_PAGE
            ),
            settings.SPIDER_MAX_EMBED_DEPTH
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
            token = getattr(session_dict["request"], "auth_token", None)
            if token:
                token = token.token
            url2 = merge_get_url(str(session_dict["sourceref"]), token=token)
            g.add(
                (
                    session_dict["sourceref"],
                    spkcgraph["action:view"],
                    URIRef(url2)
                )
            )
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
        kwargs.setdefault("legend", escape(_("View")))
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
            escape(_("Add \"%s\"") % self.__str__())
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
            escape(_("Update \"%s\"") % self.__str__())
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

    def access_anchor(self, **kwargs):
        """
            Called for anchors
            WARNING: this means the context is completely different
                     "access", "get_abilities" method of anchors
                     (and links on them) must be robust
            WARNING: it is expected that get_abilities returns "anchor"
            WARNING: it is expected that access_anchor returns a HttpResponse
        """
        raise NotImplementedError()

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
            # update function should never return HttpResponse for GET
            assert(
                not isinstance(ret, HttpResponseBase) or
                context["request"].method != "GET"
            )
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
            anchortag = "anchor\x1e"

        idtag = "primary\x1e"
        # simulates beeing not unique, by adding id
        if not unique:
            idtag = "id=\x1e"  # placeholder
            if getattr(self.associated, "id", None):
                idtag = "id={}\x1e".format(self.associated.id)
        unlistedtag = ""
        if unlisted:
            unlistedtag = "unlisted\x1e"
        return "\x1etype={}\x1e{}{}{}".format(
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
        _ = gettext
        if self.associated_obj:
            self.associated_obj.content = self
        assignedcontent = self.associated
        assignedcontent.info = self.get_info()
        if getattr(self, "id", None):
            if not self.expose_name or not assignedcontent.name:
                assignedcontent.name = self.get_content_name()
            if not self.expose_description or not assignedcontent.description:
                assignedcontent.description = self.get_content_description()
        assignedcontent.priority = self.get_priority()
        assignedcontent.strength = self.get_strength()
        assignedcontent.strength_link = self.get_strength_link()
        try:
            assignedcontent.full_clean(exclude=["content"])
        except ValidationError as exc:
            self.associated_errors = exc
        # persist AssignedContent for saving
        self.associated_obj = assignedcontent
        if self.associated_errors:
            raise ValidationError(
                _('AssignedContent validation failed'),
                code="assigned_content"
            )
        self._content_is_cleaned = True

    def save(self, *args, **kwargs):
        if settings.DEBUG:
            assert self._content_is_cleaned, "try to save uncleaned content"
        super().save(*args, **kwargs)
        assignedcontent = self.associated
        if not assignedcontent.content:
            # add requires this, needs maybe no second save
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
            if "\x1eprimary\x1e" not in assignedcontent.info:
                assignedcontent.info = assignedcontent.info.replace(
                    "\x1eid=\x1e", "\x1eid={}\x1e".format(
                        assignedcontent.id
                    ), 1
                )
                to_save.add("info")
            if (
                assignedcontent.token_generate_new_size is None and
                not assignedcontent.token
            ):
                if self.force_token_size:
                    assignedcontent.token_generate_new_size = \
                        self.force_token_size
                else:
                    assignedcontent.token_generate_new_size = \
                        getattr(settings, "INITIAL_STATIC_TOKEN_SIZE", 30)
            # set token
            if assignedcontent.token_generate_new_size is not None:
                if assignedcontent.token:
                    print(
                        "Old nonce for Content id:", assignedcontent.id,
                        "is", assignedcontent.token
                    )
                assignedcontent.token = create_b64_id_token(
                    assignedcontent.id,
                    "_",
                    assignedcontent.token_generate_new_size
                )
                assignedcontent.token_generate_new_size = None
                to_save.add("token")
            if not self.expose_name or not assignedcontent.name:
                assignedcontent.name = self.get_content_name()
                to_save.add("name")
            if not self.expose_description or not assignedcontent.description:
                assignedcontent.description = self.get_content_description()
                to_save.add("description")
            # second save required
            if to_save:
                assignedcontent.save(update_fields=to_save)
        # needs id first
        s = set(assignedcontent.attached_contents.all())
        s.update(self.get_references())
        assignedcontent.references.set(s)
        # delete saved errors
        self.associated_errors = None
        # require cleaning again
        self._content_is_cleaned = False
