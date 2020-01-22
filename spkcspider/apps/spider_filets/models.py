
import logging
import posixpath

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from spkcspider.apps.spider.conf import (
    image_extensions, media_extensions
)
from spkcspider.apps.spider.models import DataContent
from spkcspider.apps.spider.abstract_models import BaseContent
from spkcspider.apps.spider import registry
from spkcspider.constants import VariantType
from spkcspider.utils.fields import prepare_description, add_by_field

from .conf import LICENSE_CHOICES

logger = logging.getLogger(__name__)


# Create your models here.


@add_by_field(registry.contents, "_meta.model_name")
class DisclaimerFeature(BaseContent):
    appearances = [
        {
            "name": "EUDisclaimer",
            "ctype": (
                VariantType.content_feature + VariantType.unlisted
            ),
            "valid_feature_for": ["Text"]
        }
    ]

    class Meta(BaseContent.Meta):
        abstract = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", name)


class LicenseMixin(object):
    license_name_translation_list = LICENSE_CHOICES

    @property
    def full_license_name(self):
        license_name = self.free_data.get("license_name", "other")
        return self.license_name_translation_list.get(
            license_name, {}
        ).get("name", license_name)


@add_by_field(registry.contents, "_meta.model_name")
class FileFilet(LicenseMixin, DataContent):
    expose_name = True
    expose_description = True

    appearances = [{"name": "File"}]

    class Meta:
        proxy = True

    def get_template_name(self, scope):
        if scope in ["add", "update"]:
            return 'spider_filets/file_form.html'
        return 'spider_base/view_form.html'

    def get_content_name(self):
        # in case no name is set

        if self.prepared_attachements:
            fob = self.prepared_attachements["attachedfiles"][0].file
        else:
            fob = self.associated.attachedfiles.get(name="file").file
        return posixpath.basename(fob.file.name)

    def get_info(self):
        ret = super().get_info()
        split = self.associated.name.rsplit(".", 1)
        ftype = "binary"
        if len(split) == 2:
            extension = split[1].lower()
            if extension in image_extensions:
                ftype = "image"
            elif extension in media_extensions:
                ftype = "media"
        return "%sname=%s\x1efile_type=%s\x1e" % (
            ret, self.associated.name, ftype
        )

    def get_form(self, scope):
        from .forms import FileForm
        return FileForm

    def get_abilities(self, context):
        return {"download"}

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
        kwargs["file"] = self.associated.attachedfiles.get(name="file").file
        kwargs["type"] = self.associated.getlist("file_type", 1)
        if kwargs["type"]:
            kwargs["type"] = kwargs["type"][0]
        else:
            kwargs["type"] = None
        if getattr(settings, "FILE_DIRECT_DOWNLOAD", False):
            kwargs["download"] = kwargs["file"].url
        else:
            kwargs["download"] = "{}?{}".format(
                reverse(
                    'spider_base:ucontent-access',
                    kwargs={
                        "token": self.associated.token,
                        "access": 'download'
                    }
                ), kwargs["sanitized_GET"]
            )
        return render_to_string(
            "spider_filets/file.html", request=kwargs["request"],
            context=kwargs
        )

    def access_download(self, **kwargs):
        f = self.associated.attachedfiles.get(name="file")
        if getattr(settings, "FILE_DIRECT_DOWNLOAD", False):
            response = f.get_response()
        else:
            response = f.get_response(
                name=self.associated.name, request=kwargs["request"],
                add_extension=True
            )

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


@add_by_field(registry.contents, "_meta.model_name")
class TextFilet(LicenseMixin, DataContent):
    expose_name = "force"
    expose_description = True

    appearances = [{"name": "Text"}]

    class Meta:
        proxy = True

    def get_priority(self):
        # push to top
        if self.free_data.get("push"):
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
        if self.prepared_attachements:
            t = self.prepared_attachements["attachedblobs"][0]
        else:
            t = self.associated.attachedblobs.filter(name="text").first()
        return " ".join(
            prepare_description(
                t.as_bytes.decode("utf8") if t else "", 51
            )[:50]
        )

    def get_info(self):
        ret = super().get_info()
        return "%sname=%s\x1efile_type=text\x1e" % (
            ret, self.associated.name

        )

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
        if source.id in self.free_data.get("editable_from", []):
            _abilities.add("update_guest")
        return _abilities

    def access_update_guest(self, **kwargs):
        kwargs["legend"] = \
            escape(_("Update \"%s\" (guest)") % self.__str__())
        kwargs["inner_form"] = False
        return self.access_update(**kwargs)

    def access_view(self, **kwargs):
        kwargs["object"] = self
        kwargs["text"] = \
            self.associated.attachedblobs.get(name="text").as_bytes.decode(
                "utf8"
            )
        return render_to_string(
            "spider_filets/text.html", request=kwargs["request"],
            context=kwargs
        )
