
import base64
import json
from django.conf import settings
from django.db import models
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from jsonfield import JSONField


from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)
CACHE_FORMS = {}

# Create your models here.


# @add_content
class TagLayout(models.Model):
    # TagLayout has ctype "" = private
    appearances = [("TagLayout", "")]
    name = models.CharField(max_length=255, null=False)
    layout = JSONField(default=[])
    default_verifiers = JSONField(default=[])
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="+", null=True,
        on_delete=models.CASCADE
    )

    def get_form(self):
        from .forms import generate_form
        form = CACHE_FORMS.get((self.variant.owner, self.variant.name))
        if not form:
            form = generate_form(self.layout)
            CACHE_FORMS[self.variant.owner, self.variant.name] = form
        return form

    def render(self, **kwargs):
        from .forms import TagLayoutForm
        if kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Tag Layout")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Tag Layout")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = TagLayoutForm(
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = TagLayoutForm(
                    instance=kwargs["form"].save()
                )
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )


@add_content
class SpiderTag(BaseContent):
    appearances = [("SpiderTag", UserContentType.public.value)]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,

    )
    tagdata = JSONField(default={})
    verfied_by = JSONField(default=[])

    def render(self, **kwargs):
        from .forms import SpiderTagForm
        if kwargs["scope"] == "add":
            kwargs["form"] = SpiderTagForm(
                user=kwargs["request"].user,
                **self.get_form_kwargs(kwargs["request"])
            )
            kwargs["legend"] = _("Create Tag")
            kwargs["confirm"] = _("Create")
        else:
            kwargs["form"] = self.layout.get_form(
                uc=self.associated.usercomponent,
                **self.get_form_kwargs(kwargs["request"])
            )
        if kwargs["scope"] == "update":
            kwargs["legend"] = _("Update Tag")
            kwargs["confirm"] = _("Update")

            if kwargs["form"].is_valid() and kwargs["form"].has_changed():
                self.tagdata = kwargs["form"].encoded_data
                self.verfied_by = []
                self.save()
                kwargs["form"] = self.tagtype.get_form()(
                    initial=self.tagdata
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
            return render_to_string(
                "spider_keys/tag_view.html", request=kwargs["request"],
                context=kwargs
            )

    def encode_verifiers(self):
        return ",".join(
            map(
                lambda x: base64.b64_urlencode(x),
                self.instance.verfied_by
            )
        )

    def get_info(self, usercomponent):

        return "%sverified_by=%s;tag=%s;" % (
            super().get_info(usercomponent),
            self.encode_verifiers(),
            self.cleaned_data["tagtype"]
        )
