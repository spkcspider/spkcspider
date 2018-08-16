
import logging
import posixpath
import html

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.http import FileResponse
from django.http import HttpResponseRedirect
from django.core.files.storage import default_storage


from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.helpers import token_nonce
from spkcspider.apps.spider.constants import UserContentType

logger = logging.getLogger(__name__)


# Create your models here.

def get_file_path(instance, filename):
    ret = getattr(settings, "FILET_FILE_DIR", "file_filet")
    size = getattr(settings, "FILE_NONCE_SIZE", 45)
    # try 100 times to find free filename
    # but should not take more than 1 try
    for _i in range(0, 100):
        ret_path = posixpath.join(
            ret, str(instance.associated.usercomponent.user.pk),
            token_nonce(size), filename
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise Exception("Unlikely event: no free filename")
    return ret_path


@add_content
class FileFilet(BaseContent):
    appearances = [("File", UserContentType.public.value)]

    add = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=255, null=False)

    file = models.FileField(upload_to=get_file_path)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        name = self.name
        if "." not in name:  # use saved ending
            ext = self.file.name.rsplit(".", 1)
            if len(ext) > 1:
                name = "%s.%s" % (name, ext[1])
        return "%s: %s" % (
            self.localize_name(self.associated.ctype.name),
            name
        )

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%sname=%s;" % (ret, self.name)

    def render(self, **kwargs):
        from .forms import FileForm
        if kwargs["scope"] in ["update", "add"]:
            kwargs["enctype"] = "multipart/form-data"
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
            if kwargs["scope"] in ["add", "update"]:
                template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            if getattr(settings, "FILET_DIRECT_DOWNLOAD", False):
                response = HttpResponseRedirect(
                    self.file.url,
                )
            else:
                response = FileResponse(
                    self.file.file,
                    content_type='application/force-download'
                )
            name = self.name
            if "." not in name:  # use saved ending
                ext = self.file.name.rsplit(".", 1)
                if len(ext) > 1:
                    name = "%s.%s" % (name, ext[1])
            response['Content-Disposition'] = \
                'attachment; filename=%s' % html.escape(name)
            return response

    def save(self, *args, **kw):
        if self.pk is not None:
            orig = FileFilet.objects.get(pk=self.pk)
            if orig.file != self.file:
                orig.file.delete(False)
        super().save(*args, **kw)


@add_content
class TextFilet(BaseContent):
    appearances = [
        (
            "Text", UserContentType.public.value +
            UserContentType.link.value
        )
    ]

    name = models.CharField(max_length=255, null=False)
    non_public_edit = models.BooleanField(
        default=False,
        help_text=_("Allow others to edit text file if not public")
    )

    text = models.TextField(default="")

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%sname=%s;" % (ret, self.name)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        _i = self.name
        return "%s: %s" % (self.localize_name(self.associated.ctype.name), _i)

    def render(self, **kwargs):
        from .forms import TextForm
        if self.id:
            kwargs["legend"] = _("Update")
            kwargs["confirm"] = _("Update")
        else:
            kwargs["legend"] = _("Create")
            kwargs["confirm"] = _("Create")

        is_owner = self.is_owner(kwargs["request"].user)
        source = kwargs.get("source", None)
        allow_edit = False
        if self.non_public_edit:
            if source and not source.associated.usercomponent.public:
                allow_edit = True
            elif not source and not self.associated.usercomponent.public:
                allow_edit = True

        if not is_owner and not allow_edit:
            kwargs["legend"] = _("View")
            kwargs["no_button"] = True
        kwargs["form"] = TextForm(
            user=kwargs["request"].user,
            source=kwargs.get("source", None),
            **self.get_form_kwargs(kwargs["request"])
        )
        if kwargs["form"].is_valid() and kwargs["form"].has_changed():
            kwargs["form"] = TextForm(
                source=kwargs.get("source", None),
                user=kwargs["request"].user, instance=kwargs["form"].save()
            )
        template_name = "spider_base/full_form.html"
        if kwargs["scope"] in ["add", "update"]:
            template_name = "spider_base/base_form.html"
        return render_to_string(
            template_name, request=kwargs["request"],
            context=kwargs
        )
