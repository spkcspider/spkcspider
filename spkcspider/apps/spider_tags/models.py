
import logging
from itertools import chain

from rdflib import URIRef

from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from django.views.decorators.csrf import csrf_exempt
from jsonfield import JSONField
from spkcspider.apps.spider.abstract_models import BaseContent
from spkcspider.apps.spider.models import DataContent
from spkcspider.apps.spider import registry
from spkcspider.constants import ActionUrl, VariantType
from spkcspider.utils.settings import get_settings_func
from spkcspider.utils.fields import add_by_field

from .generators import generate_form

logger = logging.getLogger(__name__)

# Create your models here.


class TagLayout(models.Model):
    name = models.SlugField(max_length=255, null=False)
    # shall it be unique for a component?
    unique = models.BooleanField(default=False, blank=True)
    layout = JSONField(
        default=list,
        help_text=_("Field list in JSON format")
    )
    default_verifiers = JSONField(default=list, blank=True)
    usertag = models.OneToOneField(
        "spider_base.AssignedContent", on_delete=models.CASCADE,
        related_name="+", null=True, blank=True
    )
    description = models.TextField(default="", blank=True)

    class Meta(object):
        unique_together = [
            ("name", "usertag")
        ]

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Tag Layout")

    def get_description(self):
        return self.description

    def full_clean(self, **kwargs):
        # checked with clean
        kwargs.setdefault("exclude", []).append("usertag")
        return super().full_clean(**kwargs)

    def clean(self):
        if self.usertag:
            if TagLayout.objects.filter(usertag=None, name=self.name).exists():
                raise ValidationError(
                    _("Layout exists already"),
                    code="unique"
                )
            self.usertag.full_clean(exclude=["layout"])

    def get_form(self):
        return generate_form("LayoutForm", self.layout)

    def __repr__(self):
        if self.usertag:
            return "<TagLayout: %s:%s>" % (
                self.name, self.usertag.associated.usercomponent.username
            )
        return "<TagLayout: %s>" % self.name

    def __str__(self):
        if self.usertag:
            return "TagLayout: %s:%s" % (
                self.name,
                self.usertag.associated.usercomponent.username
            )
        return "TagLayout: %s" % self.name


@add_by_field(registry.contents, "_meta.model_name")
class UserTagLayout(DataContent):
    # 10 is required for preventing info leak gadgets via component auth
    appearances = [
        {
            "name": "TagLayout",
            "ctype": VariantType.unique,
            "strength": 10
        }
    ]
    expose_name = False
    expose_description = True

    class Meta:
        proxy = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Tag Layout")

    def get_content_name(self):
        return "%s: %s" % (
            self.associated.usercomponent.username,
            self.layout.name,
        )

    def localized_description(self):
        """ localize and perform other transforms before rendering to user """
        return gettext(self.associated.description)

    def get_size(self, prepared_attachements=None):
        s = super().get_size(prepared_attachements)
        s += len(str(self.layout.default_verifiers))
        s += len(str(self.layout.layout))
        return s

    def get_template_name(self, scope):
        if scope == "view":
            return 'spider_tags/edit_preview_form.html'
        return super().get_template_name(scope)

    def get_strength_link(self):
        # never allow links to this, elsewise with links is an information
        # disclosure possible
        return 11

    def get_info(self):
        return "%slayout=%s\x1e" % (
            super().get_info(),
            self.layout.name
        )

    def get_form(self, scope):
        if scope in {"add", "update", "export"}:
            from .forms import TagLayoutForm
            return TagLayoutForm
        else:
            return self.layout.get_form()

    def access_view(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            escape(_("Check \"%s\"") % self.__str__())
        )
        # not visible by default
        kwargs.setdefault("confirm", _("Check"))
        # prevent second button
        kwargs.setdefault("inner_form", False)
        return super().access_view(**kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs["instance"] = self.layout
        ret = super().get_form_kwargs(**kwargs)
        if kwargs["scope"] in {"add", "update", "export"}:
            ret["usertaglayout"] = self
        return ret

    def access(self, context):
        if context["scope"] == "view":
            context["extra_outer_forms"] = ["request_verification_form"]
        return super().access(context)

    @property
    def layout(self):
        tlayout = None
        if getattr(self.associated, "pk", None):
            tlayout = TagLayout.objects.filter(usertag=self.associated).first()
        if not tlayout:
            tlayout = TagLayout(usertag=self.associated)
        return tlayout


@add_by_field(registry.contents, "_meta.model_name")
class SpiderTag(BaseContent):
    # cannot optimize into a DataContent, too many ForeignKeys
    _cached_references = None
    tmp_primary_anchor = None
    appearances = [
        {
            "name": "SpiderTag",
            "strength": 0,
            "ctype": VariantType.domain_mode
        },
        {
            "name": "PushedTag",
            "strength": 2,
            "ctype": VariantType.component_feature + VariantType.domain_mode
        }
    ]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,
    )
    tagdata = JSONField(default=dict, blank=True)
    verified_by = JSONField(default=list, blank=True)
    updateable_by = models.ManyToManyField(
        "spider_base.ReferrerObject", related_name="tags", blank=True
    )
    primary = models.BooleanField(default=False, blank=True)

    expose_name = False
    expose_description = False

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        if not self.layout.usertag:
            return "%s: <%s>: %s" % (
                self.localize_name("SpiderTag"),
                self.layout.name,
                self.associated_id
            )
        return "%s: <%s: %s>: %s" % (
            self.localize_name("SpiderTag"),
            self.layout.usertag.usercomponent.username,
            self.layout.name,
            self.associated_id
        )

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        if name == "PushedTag":
            return _("content name", "Allow receiving tags")
        else:
            return _("content name", "Tag")

    @classmethod
    def feature_urls(cls, name):
        return [
            ActionUrl("pushtag", reverse("spider_tags:create-pushtag"))
        ]

    def get_content_description(self):
        return self.layout.get_description()

    def get_content_name(self):
        if not self.layout.usertag:
            return self.layout.name
        return self.layout.usertag.content.get_content_name()

    def get_template_name(self, scope):
        if scope == "update":
            return 'spider_tags/edit_form.html'
        if scope == "push_update":
            return 'spider_base/edit_form.html'
        return super().get_template_name(scope)

    def get_size(self, prepared_attachements=None):
        s = super().get_size(prepared_attachements)
        s += len(str(self.verified_by))
        s += len(str(self.tagdata))
        return s

    def get_strength_link(self):
        return 0

    def get_abilities(self, context):
        _abilities = set()
        if (
            context["request"].auth_token and
            context["request"].auth_token.referrer
        ):
            if get_settings_func(
                "SPIDER_TAG_VERIFIER_VALIDATOR",
                "spkcspider.apps.spider.functions.clean_verifier"
            )(context["request"], self):
                _abilities.add("verify")
            if self.updateable_by.filter(
                id=context["request"].auth_token.referrer_id
            ).exists():
                _abilities.add("push_update")

        return _abilities

    def map_data(self, name, field, data, graph, context):
        if (
            field.__class__.__name__ == "AnchorField" and
            field.use_default_anchor
        ):
            if data is None:
                return URIRef(self.get_primary_anchor(graph, context))
        return super().map_data(name, field, data, graph, context)

    @csrf_exempt
    def access_verify(self, **kwargs):
        # full url to result
        verified = kwargs["request"].POST.get("url", "")
        if "://" not in verified:
            return HttpResponse("invalid url", status=400)
        if verified in self.verified_by:
            return self.access_view(**kwargs)
        self.verified_by.append(verified)
        self.clean()
        self.save()

        return self.access_view(**kwargs)

    def access_push_update(self, **kwargs):
        kwargs["legend"] = escape(
            _("Update \"%s\" (push)") % self.__str__()
        )
        kwargs["inner_form"] = False
        return self.access_update(**kwargs)

    def access(self, context):
        if context["scope"] not in {"add", "view"}:
            context["extra_outer_forms"] = ["request_verification_form"]
        return super().access(context)

    def get_form(self, scope):
        from .forms import SpiderTagForm
        if scope == "add":
            return SpiderTagForm
        else:
            return self.layout.get_form()

    def get_references(self):
        if not getattr(self, "layout", None):
            return super().get_references()
        if self._cached_references is None:
            form = self.layout.get_form()(
                initial=self.tagdata.copy(),
                instance=self,
                uc=self.associated.usercomponent
            )
            _cached_references, needs_update = form.calc_references(True)
            if needs_update:
                self.associated.save(
                    update_fields=[
                        "attached_to_primary_anchor"
                    ]
                )
            self._cached_references = _cached_references
        return chain(
            self._cached_references,
            super().get_references()
        )

    def get_form_kwargs(self, instance=None, **kwargs):
        if kwargs["scope"] == "add":
            ret = super().get_form_kwargs(
                instance=instance,
                **kwargs
            )
            ret["user"] = self.associated.usercomponent.user
        else:
            ret = super().get_form_kwargs(
                **kwargs
            )
            ret["initial"] = self.tagdata.copy()
            ret["request"] = kwargs["request"]
            ret["uc"] = self.associated.usercomponent
        return ret

    def encode_verifiers(self):
        return "".join(
            map(
                lambda x: "verified_by={}\x1e".format(x),
                self.verified_by
            )
        )

    def get_info(self):
        return "{}{}tag={}\x1e".format(
            super().get_info(unique=self.primary, unlisted=False),
            self.encode_verifiers(),
            self.layout.name
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._cached_references = None
