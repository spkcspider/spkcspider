
__all__ = ("BaseContent",)

import logging
from datetime import timedelta
from urllib.parse import urljoin

from rdflib import RDF, XSD, BNode, Graph, Literal, URIRef

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.files.base import File
from django.db import models, transaction
from django.http import Http404
from django.http.response import HttpResponse, HttpResponseBase
from django.middleware.csrf import CsrfViewMiddleware
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.translation import gettext, pgettext
from django.views.decorators.csrf import csrf_exempt
from spkcspider.constants import VariantType, spkcgraph
from spkcspider.utils.fields import add_property, literalize
from spkcspider.utils.security import create_b64_id_token
from spkcspider.utils.settings import get_settings_func
from spkcspider.utils.urls import merge_get_url

from ..conf import get_anchor_domain
from ..serializing import paginate_stream, serialize_stream

logger = logging.getLogger(__name__)


# don't spam set objects
_empty_set = frozenset()

_blacklisted = set(getattr(
    settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
))

default_abilities = frozenset(
    {"add", "view", "update", "export", "list", "raw", "raw_update"}
)

# never use these names
forbidden_names = {"Content", "UserComponent"}


class BaseContent(models.Model):
    # consider not writing admin wrapper for (sensitive) inherited content
    # this way content could be protected to be only visible to admin, user
    # and legitimated users (if not index)

    id: int = models.BigAutoField(primary_key=True, editable=False)
    # every content can specify its own deletion period
    deletion_period = getattr(
        settings, "SPIDER_CONTENTS_DEFAULT_DELETION_PERIOD", timedelta(0)
    )
    # use usercomponent in form instead
    associated = models.OneToOneField(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE, null=True
    )

    # internal check if clean was executed
    _content_is_cleaned = False

    # autofilled set with attachement object names
    attached_attributenames = set()

    # transfer attribute for errors of associated
    associated_errors = None

    class Meta:
        abstract = True
        default_permissions = ()

    #################################################################

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
    # None or dict (key=related_name)
    prepared_attachements = None
    # user can set name
    # if set to "force" name will be enforced
    expose_name = True
    # user can set description
    expose_description = False
    # use if you want to force a token size
    force_token_size = None
    # extra size which should be used in calc
    extra_size = 0

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        else:
            return self.associated.name

    def __repr__(self):
        return "<Content: ({}: {})>".format(
            self.associated.usercomponent.username, self.__str__()
        )

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
            ob.associated = associated
        else:
            from ..models import AssignedContent
            if not associated_kwargs:
                associated_kwargs = {}
            ob = cls(associated=AssignedContent(**associated_kwargs))
            # abuse cached_property mechanic
            ob.associated.__dict__["content"] = ob
        if token_size is not None:
            ob.associated.token_generate_new_size = token_size
        return ob

    @classmethod
    def localize_name(cls, name):
        """
            Localize type names
        """
        return pgettext("content name", name)

    def get_size(self, prepared_attachements=None):
        from ..models.content_extended import BaseAttached
        # 255 = length name, ignore potential utf8 encoding differences
        s = 255
        if self.expose_description:
            s += len(self.associated.description)
        if prepared_attachements is not None:
            for val in prepared_attachements.values():
                if not hasattr(val, "__iter__"):
                    val = [val]
                for ob in val:
                    if isinstance(ob, BaseAttached):
                        s += ob.get_size()
        else:
            for attached in self.attached_attributenames:
                for ob in getattr(self.associated, attached).all():
                    s += ob.get_size()
        return s

    def get_priority(self):
        return 0

    @classmethod
    def feature_urls(cls, name):
        """ For implementing component features """
        return []

    def get_content_name(self):
        return "{}_{}".format(
            self.localize_name(self.associated.ctype.name),
            self.associated_id
        )

    def get_content_description(self):
        return " "

    def localized_description(self):
        """ localize and perform other transforms before rendering to user """
        if self.expose_description:
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

    def get_propagate_modified(self):
        return "\x1eunlisted\x1e" not in self.associated.info

    def get_form_kwargs(
        self, request, instance=None, disable_data=False, **kwargs
    ):
        """Return the keyword arguments for instantiating the form."""
        fkwargs = {}
        if instance:
            fkwargs["instance"] = instance
        else:
            fkwargs["instance"] = self

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
        if VariantType.component_feature in self.associated.ctype.ctype:
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
                    instance.get_size(self.prepared_attachements) - old_size
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
        return {
            "content": render_to_string(
                self.get_template_name(scope),
                request=kwargs["request"], context=kwargs
            ),
            "media": kwargs["form"].media
        }

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
        """
            For specifing references to other contents.
            Defaults to smarttag targets + attached_to_content
        """
        from ..models import AssignedContent
        return AssignedContent.objects.filter(
            models.Q(smarttag_sources__content=self.associated) |
            models.Q(attached_contents=self.associated)
        )

    def map_data(self, name, field, data, graph, context):
        if isinstance(data, File):
            return get_settings_func(
                "SPIDER_FILE_EMBED_FUNC",
                "spkcspider.apps.spider.functions.embed_file_default"
            )(name, data, self, context)
        return literalize(data, field, domain_base=context["hostpart"])

    def serialize(self, graph, ref_content, context):
        # context may not be updated here
        form = self.get_form(context["scope"])(
            **self.get_form_kwargs(
                disable_data=True,
                **context
            )
        )

        # context["abilities"] cache available if accessed via access
        # cannot update without breaking serializing, embed
        if "abilities" in context:
            abilities = context["abilities"]
        else:
            abilities = set(self.get_abilities(context))

        for ability in abilities:
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
            if not value:
                graph.add((
                    value_node,
                    spkcgraph["value"],
                    RDF.nil
                ))

    def render_serialize(self, **kwargs):
        from ..models import AssignedContent
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
            AssignedContent.objects.filter(id=self.associated_id),
            getattr(
                settings, "SPIDER_SERIALIZED_PER_PAGE",
                settings.SPIDER_OBJECTS_PER_PAGE
            ),
            settings.SPIDER_MAX_EMBED_DEPTH
        )
        page = 1
        try:
            page = int(session_dict["request"].GET.get("page", "1"))
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
            source = kwargs.get("source", self)
            # "expires" (string) different from "token_expires" (datetime)
            if session_dict.get("expires"):
                add_property(
                    g, "token_expires", ob=session_dict["request"],
                    ref=session_dict["sourceref"]
                )
            if kwargs.get("machine_variants"):
                assert kwargs["request"].is_owner
                ucref = URIRef(urljoin(
                    kwargs["hostpart"],
                    source.associated.usercomponent.get_absolute_url()
                ))
                for machinec in kwargs["machine_variants"]:
                    g.add((
                        ucref,
                        spkcgraph["create:name"],
                        Literal(machinec, datatype=XSD.string)
                    ))
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(kwargs["scope"], datatype=XSD.string)
            ))

            uc = kwargs.get("source", self.associated.usercomponent)
            g.add((
                session_dict["sourceref"], spkcgraph["strength"],
                Literal(uc.strength, datatype=XSD.integer)
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
        return {
            "content": render_to_string(
                self.get_template_name(kwargs["scope"]),
                request=kwargs["request"],
                context=kwargs
            ),
            "media": kwargs["form"].media
        }

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
        if VariantType.no_export in self.associated.ctype.ctype:
            raise Http404()
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
                context["content"] = csrferror
                return context
        ret = func(**context)
        # update function should never return HttpResponse for GET
        if isinstance(ret, HttpResponseBase):
            assert (
                context["scope"] != "update" or
                context["request"].method != "GET"
            )
            context["content"] = ret
        elif isinstance(ret, str):
            context["content"] = ret
        elif isinstance(ret, dict):
            oldmedia = context["media"]
            context.update(ret)
            context["media"] += oldmedia
        else:
            raise NotImplementedError()
        return context

    def get_info(self, unique=None, unlisted=None):
        # unique=None, feature=None shortcuts for get_info overwrites
        # passing down these parameters not neccessary
        if unique is None:
            unique = (
                VariantType.unique in self.associated.ctype.ctype
            )
        if unlisted is None:
            unlisted = (
                VariantType.component_feature in
                self.associated.ctype.ctype or
                VariantType.content_feature in
                self.associated.ctype.ctype
            )

        anchortag = ""
        if VariantType.anchor in self.associated.ctype.ctype:
            anchortag = "anchor\x1e"

        idtag = "primary\x1e"
        # simulates beeing not unique, by adding id
        if not unique:
            idtag = "id=\x1e"  # placeholder
            if getattr(self.associated, "id", None):
                idtag = "id={}\x1e".format(self.associated_id)
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
        kwargs.setdefault("exclude", []).append("associated")
        return super().full_clean(**kwargs)

    def update_associated(self):
        if getattr(self, "id", None):
            self.associated.info = self.get_info()
            if not self.expose_name or not self.associated.name:
                self.associated.name = self.get_content_name()
            if not self.expose_description or not self.associated.description:
                self.associated.description = self.get_content_description()
        self.associated.priority = self.get_priority()
        self.associated.strength = self.get_strength()
        self.associated.strength_link = self.get_strength_link()

    def clean(self):
        _ = gettext
        self.update_associated()
        try:
            self.associated.full_clean(exclude=["datacontent"])
        except ValidationError as exc:
            self.associated_errors = exc
        if self.associated_errors:
            raise ValidationError(
                _('AssignedContent validation failed'),
                code="assigned_content"
            )
        self._content_is_cleaned = True

    def save(self, *args, **kwargs):
        if settings.DEBUG:
            assert self._content_is_cleaned, "try to save uncleaned content"
        created = False
        assignedcontent = self.associated
        if not getattr(self, "id", None):
            created = True
            # create the model for saving BaseContent
            assignedcontent.save()
        # this changes the associated model for no reason
        super().save(*args, **kwargs)
        # restore it here
        self.associated = assignedcontent
        if created:
            # add requires this
            self.update_associated()
        if not self.associated.token:
            if self.force_token_size:
                self.associated.token_generate_new_size = \
                    self.force_token_size
            else:
                self.associated.token_generate_new_size = \
                    getattr(settings, "INITIAL_STATIC_TOKEN_SIZE", 30)
        # set token
        if self.associated.token_generate_new_size is not None:
            if self.associated.token:
                print(
                    "Old nonce for Content id:", self.associated_id,
                    "is", self.associated.token
                )
            self.associated.token = create_b64_id_token(
                self.associated_id,
                "_",
                self.associated.token_generate_new_size
            )
            self.associated.token_generate_new_size = None
        # save associated
        self.associated.save()

        if self.prepared_attachements:
            for key, val in self.prepared_attachements.items():
                if not hasattr(val, "__iter__"):
                    val = [val]
                pks = set()
                for i in val:
                    i.save()
                    pks.add(i.pk)
                # remove rest (if foreignkey)
                fieldmanager = getattr(self.associated, key)
                field = self.associated._meta.get_field(key)
                if field.many_to_many:
                    fieldmanager.set(val)
                elif field.one_to_many:
                    fieldmanager.exclude(pk__in=pks).delete()
        # needs id first
        self.associated.references.set(self.get_references())
        # message usercomponent about change
        if self.get_propagate_modified():
            self.associated.usercomponent.save(update_fields=["modified"])
        # delete saved errors
        self.associated_errors = None
        # require cleaning again
        self._content_is_cleaned = False
        # reset to default
        self.prepared_attachements = None
