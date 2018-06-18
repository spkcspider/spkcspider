
import logging
import posixpath
import html

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.http import FileResponse


from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)

from spkcspider.apps.spider.helpers import (
    token_nonce
)


logger = logging.getLogger(__name__)


# Create your models here.

def get_file_path(instance, filename):
    ret = getattr(settings, "FILET_FILE_DIR", "/")
    split = filename.rsplit(".", 1)
    ret = posixpath.join(ret, token_nonce())
    if len(split) > 1:
        ret = "%s.%s" % (ret, split[1])
    return ret


@add_content
class FileFilet(BaseContent):
    names = ["File"]
    ctype = UserContentType.public.value
    is_unique = False

    add = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=255, null=False, editable=False)

    file = models.FileField(get_file_path)

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%sname=%s;" % (ret, self.name)

    def render(self, **kwargs):
        from .forms import FileForm
        if kwargs["scope"] == "download":
            response = FileResponse(
                self.file.file,
                content_type='application/force-download'
            )
            response['Content-Disposition'] = \
                'attachment; filename=%s' % html.escape(self.name)
            return response
        elif kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update File")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Upload File")
                kwargs["confirm"] = _("Upload")
            kwargs["form"] = FileForm(
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = FileForm(
                    instance=kwargs["form"].save()
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
                "spider_keys/file.html", request=kwargs["request"],
                context=kwargs
            )

    def save(self, *args, **kw):
        if self.pk is not None:
            orig = FileFilet.objects.get(pk=self.pk)
            if orig.file != self.file:
                orig.file.delete()
        super().save(*args, **kw)


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
        from .forms import TextForm
        if self.id:
            if self.request.user in self.edit_allowed:
                kwargs["legend"] = _("Update")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("View")
                kwargs["confirm"] = _("")
        else:
            kwargs["legend"] = _("Create")
            kwargs["confirm"] = _("Create")
        kwargs["form"] = TextForm(
            user=self.request.user,
            **self.get_form_kwargs(kwargs["request"])
        )
        if kwargs["form"].is_valid():
            kwargs["form"] = TextForm(
                user=self.request.user, instance=kwargs["form"].save()
            )
        template_name = "spider_base/full_form.html"
        if kwargs["scope"] == "update":
            template_name = "spider_base/base_form.html"
        return render_to_string(
            template_name, request=kwargs["request"],
            context=kwargs
        )
