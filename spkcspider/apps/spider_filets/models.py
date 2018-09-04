
import logging
import posixpath
import html

from django.db import models
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.http import FileResponse
from django.http import HttpResponseRedirect
from django.core.files.storage import default_storage


from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.helpers import token_nonce

logger = logging.getLogger(__name__)


# Create your models here.

def get_file_path(instance, filename):
    ret = getattr(settings, "FILET_FILE_DIR", "file_filet")
    size = getattr(settings, "FILE_NONCE_SIZE", 45)
    # try 100 times to find free filename
    # but should not take more than 1 try
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.associated.usercomponent.user.pk),
                token_nonce(size), filename
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise Exception("Unlikely event: no free filename")
    return ret_path


@add_content
class FileFilet(BaseContent):
    appearances = [{"name": "File"}]

    add = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=255, null=False)

    file = models.FileField(upload_to=get_file_path, null=False, blank=False)

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

    def get_info(self):
        ret = super().get_info()
        return "%sname=%s\n" % (ret, self.name)

    def get_form(self, scope):
        from .forms import FileForm
        return FileForm

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["request"] = kwargs["request"]
        return ret

    def render_form(self, **kwargs):
        kwargs["enctype"] = "multipart/form-data"
        return super().render_form(**kwargs)

    def render_view(self, **kwargs):
        if "raw" in kwargs["request"].GET:
            k = kwargs.copy()
            k["scope"] = "raw"
            return self.render_serialize(**k)
        kwargs["object"] = self
        kwargs["content"] = self.associated
        return render_to_string(
            "spider_filets/file.html", request=kwargs["request"],
            context=kwargs
        )

    def render_download(self, **kwargs):
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

    def render_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Upload File")
        return super().render_add(**kwargs)

    def render_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Update File")
        return super().render_update(**kwargs)

    def render(self, **kwargs):
        if kwargs["scope"] == "download":
            return self.render_download()
        return super().render(**kwargs)

    def save(self, *args, **kw):
        if self.pk is not None:
            orig = FileFilet.objects.get(pk=self.pk)
            if orig.file != self.file:
                orig.file.delete(False)
        super().save(*args, **kw)


@add_content
class TextFilet(BaseContent):
    appearances = [{"name": "Text"}]

    name = models.CharField(max_length=255, null=False)
    editable_from = models.ManyToManyField(
        "spider_base.UserComponent", related_name="+",
        help_text=_("Allow editing from selected components"
                    "by privileged users."),
        blank=True
    )

    text = models.TextField(default="")

    def get_info(self):
        ret = super().get_info()
        return "%sname=%s\n" % (ret, self.name)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        _i = self.name
        return "%s: %s" % (self.localize_name(self.associated.ctype.name), _i)

    def get_form(self, scope):
        from .forms import TextForm
        return TextForm

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["request"] = kwargs["request"]
        ret["source"] = kwargs.get("source", self.associated.usercomponent)
        return ret

    def render_view(self, **kwargs):
        if kwargs["request"].is_owner:
            kwargs["no_button"] = None
            kwargs["legend"] = _("Update \"%s\"") % self.__str__()
            kwargs["confirm"] = _("Update")
        else:
            source = kwargs.get("source", self.associated.usercomponent)
            if self.editable_from.filter(
                pk=source.pk
            ).exists():
                if kwargs["request"].is_priv_requester:
                    kwargs["no_button"] = None
                    kwargs["legend"] = _("Update \"%s\"") % self.__str__()
                    kwargs["confirm"] = _("Update")
        return super().render_view(**kwargs)
