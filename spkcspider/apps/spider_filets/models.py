
import logging
import posixpath

from django.utils.html import escape
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.http import HttpResponseRedirect
from django.core.files.storage import default_storage

from jsonfield import JSONField

from ranged_response import RangedFileResponse

from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.conf import (
    image_extensions, media_extensions
)
from spkcspider.apps.spider.helpers import (
    create_b64_token, prepare_description
)

from .conf import (
    LICENSE_CHOICES
)

logger = logging.getLogger(__name__)


# Create your models here.


def get_file_path(instance, filename):
    ret = getattr(settings, "FILE_FILET_DIR", "file_filet")
    size = getattr(settings, "FILE_FILET_SALT_SIZE", 45)
    # try 100 times to find free filename
    # but should not take more than 1 try
    # IMPORTANT: strip . to prevent creation of htaccess files or similar
    for _i in range(0, 100):
        ret_path = default_storage.generate_filename(
            posixpath.join(
                ret, str(instance.associated.usercomponent.user.pk),
                create_b64_token(size), filename.lstrip(".")
            )
        )
        if not default_storage.exists(ret_path):
            break
    else:
        raise Exception("Unlikely event: no free filename")
    return ret_path


class ContentWithLicense(BaseContent):
    license_name = models.CharField(
        max_length=255, null=False, default="other"
    )
    license_url = models.URLField(max_length=400, blank=True, null=True)
    sources = JSONField(default=list, blank=True)
    license_name_translation_list = LICENSE_CHOICES

    class Meta(BaseContent.Meta):
        abstract = True

    @property
    def full_license_name(self):
        return self.license_name_translation_list.get(
            self.license_name, {}
        ).get("name", self.license_name)

    def get_size(self):
        s = super().get_size()
        s += len(str(self.sources))
        return s


@add_content
class FileFilet(ContentWithLicense):
    expose_name = True
    expose_description = True

    appearances = [{"name": "File"}]
    file = models.FileField(upload_to=get_file_path, null=False, blank=False)

    def get_template_name(self, scope):
        if scope in ["add", "update"]:
            return 'spider_filets/file_form.html'
        return 'spider_base/view_form.html'

    def get_size(self):
        return self.file.size + super().get_size()

    def get_content_name(self):
        # in case no name is set
        return posixpath.basename(self.file.name)

    def get_info(self):
        ret = super().get_info()
        return "%sname=%s\x1e" % (ret, self.associated.name)

    def get_form(self, scope):
        from .forms import FileForm
        return FileForm

    def get_abilities(self, context):
        return set(("download",))

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["request"] = kwargs["request"]
        ret["uc"] = self.associated.usercomponent
        return ret

    def render_form(self, **kwargs):
        kwargs["enctype"] = "multipart/form-data"
        return super().render_form(**kwargs)

    def access_view(self, **kwargs):
        kwargs["object"] = self
        kwargs["associated"] = self.associated
        kwargs["type"] = None
        split = self.associated.name.rsplit(".", 1)
        if len(split) == 2:
            extension = split[1].lower()
            if extension in image_extensions:
                kwargs["type"] = "image"
            elif extension in media_extensions:
                kwargs["type"] = "media"
        if getattr(settings, "FILE_DIRECT_DOWNLOAD", False):
            kwargs["download"] = self.file.url
        else:
            kwargs["download"] = "{}?{}".format(
                reverse(
                    'spider_base:ucontent-access',
                    kwargs={
                        "token": self.associated.token,
                        "access": 'download'
                    }
                ), kwargs["spider_GET"].urlencode()
            )
        return (
            render_to_string(
                "spider_filets/file.html", request=kwargs["request"],
                context=kwargs
            ),
            ""
        )

    def access_download(self, **kwargs):
        if getattr(settings, "FILE_DIRECT_DOWNLOAD", False):
            response = HttpResponseRedirect(
                self.file.url,
            )
        else:
            response = RangedFileResponse(
                kwargs["request"],
                self.file.file,
                content_type='application/octet-stream'
            )
        name = self.associated.name
        if "." not in name:  # use ending of saved file
            ext = self.file.name.rsplit(".", 1)
            if len(ext) > 1:
                name = "%s.%s" % (name, ext[1])
        # name is sanitized to not contain \n, and other ugly control chars
        response['Content-Disposition'] = \
            'attachment; filename="%s"' % posixpath.basename(name.replace(
                r'"', r'\"'
            ))

        response["Access-Control-Allow-Origin"] = "*"
        return response

    def access_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Upload File"))
        return super().access_add(**kwargs)

    def access_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Update File"))
        return super().access_update(**kwargs)

    def save(self, *args, **kw):
        if self.pk is not None:
            orig = FileFilet.objects.get(pk=self.pk)
            if orig.file != self.file:
                orig.file.delete(False)
        super().save(*args, **kw)


@add_content
class TextFilet(ContentWithLicense):
    expose_name = "force"
    expose_description = True

    appearances = [{"name": "Text"}]

    editable_from = models.ManyToManyField(
        "spider_base.UserComponent", related_name="+",
        help_text=_("Allow editing from selected components."),
        blank=True
    )
    push = models.BooleanField(
        blank=True, default=False,
        help_text=_("Improve ranking of this content.")
    )

    text = models.TextField(default="", blank=True)

    def get_priority(self):
        # push to top
        if self.push:
            return 1
        return 0

    def get_template_name(self, scope):
        # view update form
        if scope == "update_guest":
            return 'spider_base/edit_form.html'
        elif scope == "view":
            return 'spider_base/text.html'
        return super().get_template_name(scope)

    def get_content_description(self):
        # use javascript instead
        # currently dead code
        return " ".join(
            prepare_description(
                self.text, 51
            )[:50]
        )

    def get_info(self):
        ret = super().get_info()
        return "%sname=%s\x1e" % (
            ret, self.associated.name

        )

    def get_size(self):
        return len(self.text.encode("utf8")) + super().get_size()

    def get_form(self, scope):
        if scope in ("raw", "export", "list"):
            from .forms import RawTextForm as f
        else:
            from .forms import TextForm as f
        return f

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["request"] = kwargs["request"]
        ret["source"] = kwargs.get("source", self.associated.usercomponent)
        ret["scope"] = kwargs["scope"]
        return ret

    def get_abilities(self, context):
        _abilities = set()
        source = context.get("source", self.associated.usercomponent)
        if self.id and self.editable_from.filter(
            pk=source.pk
        ).exists():
            _abilities.add("update_guest")
        return _abilities

    def access_update_guest(self, **kwargs):
        kwargs["legend"] = \
            escape(_("Update \"%s\" (guest)") % self.__str__())
        kwargs["inner_form"] = False
        return self.access_update(**kwargs)

    def access_view(self, **kwargs):

        kwargs["object"] = self
        kwargs["content"] = self.associated
        return (
            render_to_string(
                "spider_filets/text.html", request=kwargs["request"],
                context=kwargs
            ),
            ""
        )
