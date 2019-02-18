

from django.db import models
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import reverse

from jsonfield import JSONField

import requests
import certifi

from spkcspider.apps.spider.contents import (
    BaseContent, add_content, VariantType, ActionUrl
)
from spkcspider.apps.spider.helpers import get_settings_func

from spkcspider.apps.spider.models import AssignedContent
CACHE_FORMS = {}

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
        "spider_tags.UserTagLayout", on_delete=models.CASCADE,
        related_name="layout", null=True, blank=True
    )

    class Meta(object):
        unique_together = [
            ("name", "usertag")
        ]

    def clean(self):
        if TagLayout.objects.filter(usertag=None, name=self.name).exists():
            raise ValidationError(
                _("Layout exists already"),
                code="unique"
            )

    def get_form(self):
        from .forms import generate_form
        id = self.usertag.pk if self.usertag else None
        form = CACHE_FORMS.get((self.name, id))
        if not form:
            form = generate_form("LayoutForm", self.layout)
            CACHE_FORMS[self.name, id] = form
        return form

    def __repr__(self):
        return "<TagLayout: %s>" % self.name

    def __str__(self):
        return "<TagLayout: %s>" % self.name


@add_content
class UserTagLayout(BaseContent):
    appearances = [
        {
            "name": "TagLayout",
            "ctype": VariantType.unique.value,
            "strength": 10
        }
    ]

    def get_size(self):
        return len(str(self.layout.layout).encode("utf8"))

    def get_strength_link(self):
        return 11

    def get_info(self):
        return "%slayout=%s\n" % (
            super().get_info(),
            self.layout.name
        )

    def get_form(self, scope):
        if scope == "add":
            from .forms import TagLayoutForm
            return TagLayoutForm
        else:
            ret = self.layout.get_form()
            if scope not in ["update", "raw_update"]:
                for i in ret.fields:
                    i.disabled = True
            return ret

    def access_add(self, **kwargs):
        if not hasattr(self, "layout"):
            self.layout = TagLayout(usertag=self)
        return super().access_add(**kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs["instance"] = self.layout
        return super().get_form_kwargs(**kwargs)


@add_content
class SpiderTag(BaseContent):
    _cached_references = None
    appearances = [
        {
            "name": "SpiderTag",
            "strength": 0
        },
        {
            "name": "PushedTag",
            "strength": 0,
            "ctype": VariantType.feature + VariantType.domain_mode,
        }
    ]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,

    )
    tagdata = JSONField(default=dict, blank=True)
    verified_by = JSONField(default=list, blank=True)
    updateable_by = JSONField(default=list, blank=True)
    primary = models.BooleanField(default=False, blank=True)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        return "%s: %s:%s" % (
            self.localize_name("Tag"),
            self.layout.name,
            self.associated.id
        )

    @classmethod
    def feature_urls(cls):
        return [
            ActionUrl(reverse("spider_tags:create-pushtag"), "pushtag")
        ]

    def get_template_name(self, scope):
        if scope in ["add", "update", "push_update"]:
            return 'spider_tags/edit_form.html'
        return 'spider_tags/view_form.html'

    def get_size(self):
        return len(str(self.tagdata).encode("utf8"))

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
                "spkcspider.apps.spider.functions.allow_all_filter"
            )(self, context["request"]):
                _abilities.add("verify")
            if context["request"].auth_token.referrer in self.updateable_by:
                _abilities.add("push_update")
        return _abilities

    def access_verify(self, **kwargs):
        # full url to result
        verified = kwargs["request"].POST.get("verified_url", "")
        if not verified.startswith(kwargs["request"].auth_token.referrer):
            raise PermissionDenied()
        if verified in self.verified_by:
            return self.access_view(self, **kwargs)
        resp = requests.get(
            verified,
            verify=certifi.where()
        )
        if resp.status_code != 200:
            return HttpResponse(status_code=400)
        self.verified_by.append(verified)
        self.clean()
        self.save()

        return self.access_view(self, **kwargs)

    def access_push_update(self, **kwargs):
        kwargs["legend"] = _("Update \"%s\" (push)") % self.__str__()
        kwargs["inner_form"] = False
        return self.access_update(**kwargs)

    def get_form(self, scope):
        from .forms import SpiderTagForm
        if scope == "add":
            return SpiderTagForm
        else:
            return self.layout.get_form()

    def get_references(self):
        if not getattr(self, "layout", None):
            return []
        if self._cached_references:
            return self._cached_references
        _cached_references = []
        form = self.layout.get_form()(
            initial=self.tagdata.copy(),
            instance=self,
            uc=self.associated.usercomponent
        )
        for name, field in form.fields.items():
            raw_value = form.initial.get(name, None)
            value = field.to_python(raw_value)
            # e.g. anchors
            if isinstance(value, AssignedContent):
                _cached_references.append(value)

            if issubclass(type(value), BaseContent):
                _cached_references.append(value.associated)

            # e.g. anchors
            if isinstance(value, models.QuerySet):
                if issubclass(value.model, AssignedContent):
                    _cached_references += list(value)

                if issubclass(value.model, BaseContent):
                    _cached_references += list(
                        AssignedContent.objects.filter(
                            object_id__in=value.values_list(
                                "id", flat=True
                            ),
                            content_type=ContentType.objects.get_for_model(
                                value.model
                            )
                        )
                    )
        self._cached_references = _cached_references
        return self._cached_references

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
            ret["uc"] = self.associated.usercomponent
        return ret

    def encode_verifiers(self):
        return "".join(
            map(
                lambda x: "verified_by={}\n".format(
                    x.replace("\n", "%0A")
                ),
                self.verified_by
            )
        )

    def get_info(self):
        return "{}{}tag={}\n".format(
            super().get_info(unique=self.primary, unlisted=False),
            self.encode_verifiers(),
            self.layout.name
        )
