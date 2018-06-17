from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
#from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import pgettext
from django.http import HttpResponse


import logging

from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)

logger = logging.getLogger(__name__)


# Create your models here.

def get_file_dir():
    return getattr(settings, "FILET_FILE_DIR")


@add_content
class FileFilet(BaseContent):
    names = ["File"]
    ctype = UserContentType.public.value
    is_unique = False

    name = models.CharField(max_length=255, null=False, editable=False)

    file = models.FileField(get_file_dir)

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%sname=%s;" % (ret, self.name)

    def render(self, **kwargs):
        if kwargs["scope"] == "hash":
            return HttpResponse(self.hash, content_type="text/plain")
        elif kwargs["scope"] == "key":
            return HttpResponse(self.key, content_type="text/plain")
        elif kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Public Key")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Public Key")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = KeyForm(
                uc=kwargs["uc"],
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = KeyForm(
                    uc=kwargs["uc"], instance=kwargs["form"].save()
                )
            template_name = "spider_base/full_form.html"
            if kwargs["scope"] == "update":
                template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            kwargs["object"] = self
            return render_to_string(
                "spider_keys/key.html", request=kwargs["request"],
                context=kwargs
            )



@add_content
class TextFilet(BaseContent):
    names = ["Text"]
    ctype = UserContentType.public.value
    is_unique = False

    name = models.CharField(max_length=255, null=False, editable=False)
    edit_allowed = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="+"
    )

    text = models.TextField(default="")

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%sname=%s;" % (ret, self.name)

    def render(self, **kwargs):
        from .forms import KeyForm
        if kwargs["scope"] == "hash":
            return HttpResponse(self.hash, content_type="text/plain")
        elif kwargs["scope"] == "key":
            return HttpResponse(self.key, content_type="text/plain")
        elif kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Public Key")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Public Key")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = KeyForm(
                uc=kwargs["uc"],
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = KeyForm(
                    uc=kwargs["uc"], instance=kwargs["form"].save()
                )
            template_name = "spider_base/full_form.html"
            if kwargs["scope"] == "update":
                template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            kwargs["object"] = self
            return render_to_string(
                "spider_keys/key.html", request=kwargs["request"],
                context=kwargs
            )
