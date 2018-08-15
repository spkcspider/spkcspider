
import base64
import json
from django.db import models
from django.http import HttpResponse
from django.core.exceptions import NON_FIELD_ERRORS
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError

from jsonfield import JSONField


from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)
CACHE_FORMS = {}

# Create your models here.


class TagLayout(models.Model):
    name = models.SlugField(max_length=255, null=False)
    layout = JSONField(default=[])
    default_verifiers = JSONField(default=[], blank=True)
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
                code="unique"  # TODO:correct code
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
        (
            "TagLayout",
            UserContentType.confidential.value +
            UserContentType.unique.value +
            UserContentType.link.value
        )
    ]

    def get_info(self, usercomponent):
        return "%slayout=%s;" % (
            super().get_info(usercomponent),
            self.layout.name
        )

    def render(self, **kwargs):
        from .forms import TagLayoutForm
        if kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Tag Layout")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Tag Layout")
                kwargs["confirm"] = _("Create")
            if not hasattr(self, "layout"):
                self.layout = TagLayout(usertag=self)
            kwargs["form"] = TagLayoutForm(
                instance=self.layout,
                **self.get_form_kwargs(kwargs["request"], instance=False)
            )
            if kwargs["form"].is_valid() and self.full_clean():
                self.save()
                kwargs["form"] = TagLayoutForm(
                    instance=kwargs["form"].save()
                )
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            kwargs["form"] = TagLayoutForm(instance=self.layout)
            for i in kwargs["form"].fields:
                i.disabled = True
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )


@add_content
class SpiderTag(BaseContent):
    appearances = [
        ("SpiderTag", UserContentType.public.value),
    ]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,

    )
    tagdata = JSONField(default={}, blank=True)
    verified_by = JSONField(default=[], blank=True)
    primary = models.BooleanField(default=False, blank=True)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        return "%s: %s (%s)" % (
            self.localize_name("Tag"),
            self.layout.name,
            self.id
        )

    def render(self, **kwargs):
        from .forms import SpiderTagForm
        parent_form = kwargs.pop("form", None)
        if kwargs["scope"] == "add":
            kwargs["legend"] = _("Create Tag")
            kwargs["confirm"] = _("Create")
            kwargs["form"] = SpiderTagForm(
                user=kwargs["uc"].user,
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"].save()
                kwargs["form"] = self.layout.get_form()(
                    initial=self.tagdata,
                    uc=self.associated.usercomponent
                )
        elif kwargs["scope"] == "update":
            kwargs["legend"] = _("Update Tag")
            kwargs["confirm"] = _("Update")
            kwargs["form"] = self.layout.get_form()(
                initial=self.tagdata,
                uc=self.associated.usercomponent,
                **self.get_form_kwargs(kwargs["request"], False)
            )
            if kwargs["form"].is_valid():
                self.tagdata = kwargs["form"].encoded_data()
                self.primary = kwargs["form"].cleaned_data["primary"]
                self.verfied_by = []
                self.full_clean()
                self.save()
                kwargs["form"] = self.layout.get_form()(
                    initial=self.tagdata,
                    uc=self.associated.usercomponent,
                )
        else:
            kwargs["form"] = self.layout.get_form()(
                initial=self.tagdata,
                uc=self.associated.usercomponent,
            )
            del kwargs["form"].fields["primary"]
            for field in kwargs["form"].fields.values():
                field.disabled = True
        if parent_form and len(kwargs["form"].errors) > 0:
            parent_form.errors.setdefault(NON_FIELD_ERRORS, []).extend(
                kwargs["form"].errors.setdefault(NON_FIELD_ERRORS, [])
            )

        if kwargs["scope"] in ["add", "update"]:
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        elif kwargs["scope"] in "raw":
            return HttpResponse(
                json.dumps(self.tagdata),
                content_type="text/json"
            )
        else:
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )

    def encode_verifiers(self):
        return ",".join(
            map(
                lambda x: base64.b64_urlencode(x),
                self.verified_by
            )
        )

    def get_info(self, usercomponent):
        return "%sverified_by=%s;tag=%s;" % (
            super().get_info(usercomponent, unique=self.primary),
            self.encode_verifiers(),
            self.layout.name
        )
