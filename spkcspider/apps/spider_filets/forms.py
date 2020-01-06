__all__ = ["FileForm", "TextForm", "RawTextForm"]

from django import forms
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from spkcspider.apps.spider.forms.base import DataContentForm
from spkcspider.apps.spider.fields import (
    MultipleOpenChoiceField, OpenChoiceField, SanitizedHtmlField
)
from spkcspider.apps.spider.models import (
    AttachedBlob, AttachedFile, UserComponent
)
from spkcspider.apps.spider.widgets import (
    ListWidget, SelectizeWidget, TrumbowygWidget
)
from spkcspider.utils.settings import get_settings_func

from .conf import DEFAULT_LICENSE_FILE, DEFAULT_LICENSE_TEXT, LICENSE_CHOICES
from .widgets import LicenseChooserWidget

_extra = '' if settings.DEBUG else '.min'


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


def _extract_choice(item):
    return (item[0], item[1].get("name", item[0]))


class LicenseForm(DataContentForm):
    license_name = OpenChoiceField(
        label=_("License"), help_text=_("Select license"),
        choices=map(_extract_choice, LICENSE_CHOICES.items()),
        widget=LicenseChooserWidget(
            licenses=LICENSE_CHOICES
        )
    )
    license_url = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                "style": "width:100%"
            }
        )
    )
    sources = MultipleOpenChoiceField(
        required=False, initial=[],
        widget=ListWidget(
            item_label=_("Source")
        )
    )
    free_fields = {"license_name": "other"}
    quota_fields = {"license_url": "", "sources": list}

    class Media:
        js = [
            'spider_filets/licensechooser.js'
        ]


class FileForm(LicenseForm):
    request = None
    file = forms.FileField()

    def __init__(self, request, uc=None, initial=None, **kwargs):
        if initial is None:
            initial = {}
        if not getattr(kwargs.get("instance", None), "id", None):
            initial.setdefault(
                "license_name", DEFAULT_LICENSE_FILE(uc, request.user)
            )
        initial2 = {}
        if kwargs.get("instance", None):
            initial2.update(kwargs["instance"].free_data)
        initial2.update(initial)
        super().__init__(initial=initial2, **kwargs)
        if self.instance.pk:
            self.initial["file"] = \
                self.instance.associated.attachedfiles.filter(
                    name="file"
                ).first()
            if self.initial["file"]:
                self.initial["file"] = self.initial["file"].file
        setattr(self.fields['file'], "hashable", True)
        # sources should not be hashed as they don't affect result
        setattr(self.fields['sources'], "hashable", False)
        setattr(self.fields['license_name'], "hashable", True)
        setattr(self.fields['license_url'], "hashable", True)
        if request.user.is_superuser:
            # no upload limit
            pass
        elif request.user.is_staff:
            self.fields["file"].max_length = getattr(
                settings, "SPIDER_MAX_FILE_SIZE_STAFF", None
            )
        else:
            self.fields["file"].max_length = getattr(
                settings, "SPIDER_MAX_FILE_SIZE", None
            )
        if request.is_owner:
            # self.user = request.user
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False
        # for SPIDER_UPLOAD_FILTER
        self.request = request

    def clean(self):
        ret = super().clean()
        if "file" not in ret:
            return ret
        # has to raise ValidationError
        get_settings_func(
            "SPIDER_UPLOAD_FILTER",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )(self.request, ret["file"], self)
        return ret

    def get_prepared_attachements(self):
        if "file" not in self.changed_data:
            return {}
        f = None
        if self.instance.pk:
            f = self.instance.associated.attachedfiles.filter(
                name="file"
            ).first()
        if not f:
            f = AttachedFile(
                unique=True, name="file", content=self.instance.associated
            )
        f.file = self.cleaned_data["file"]
        return {
            "attachedfiles": [f]
        }


class TextForm(LicenseForm):
    text = SanitizedHtmlField(
        widget=TrumbowygWidget(
        ),
        localize=True
    )
    editable_from = forms.ModelMultipleChoiceField(
        queryset=UserComponent.objects.all(),
        required=False, initial=[],
        widget=SelectizeWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 150px; width:100%"
            }
        )
    )
    push = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Improve ranking of this Text.")
    )

    free_fields = {"push": False}
    free_fields.update(LicenseForm.free_fields)

    class Media:
        js = [
            'spider_filets/description_helper.js'
        ]

    def __init__(self, request, source, scope, initial=None, **kwargs):
        if initial is None:
            initial = {}
        if not getattr(kwargs.get("instance", None), "id", None):
            initial.setdefault(
                "license_name", DEFAULT_LICENSE_TEXT(source, request.user)
            )
        initial2 = {}
        if kwargs.get("instance", None):
            initial2.update(kwargs["instance"].free_data)
        initial2.update(initial)
        super().__init__(initial=initial2, **kwargs)
        if self.instance.pk:
            self.initial["text"] = \
                self.instance.associated.attachedblobs.filter(
                    name="text"
                ).first()
            if self.initial["text"] is not None:
                self.initial["text"] = \
                    self.initial["text"].as_bytes.decode("utf8")
        if scope in ("add", "update"):
            self.fields["editable_from"].help_text = \
                _(
                    "Allow editing from selected components. "
                    "Requires protection strength >=%s."
                ) % settings.SPIDER_MIN_STRENGTH_EVELATION

            query = models.Q(pk=self.instance.associated.usercomponent_id)
            if scope == "update":
                query |= models.Q(
                    contents__references=self.instance.associated
                )
            query &= models.Q(
                strength__gte=settings.SPIDER_MIN_STRENGTH_EVELATION
            )
            query &= models.Q(strength__lt=9)
            self.fields["editable_from"].queryset = \
                self.fields["editable_from"].queryset.filter(query).distinct()
            return

        del self.fields["editable_from"]
        del self.fields["push"]
        self.fields["license_name"].editable = False
        self.fields["license_url"].editable = False

        allow_edit = scope == "update_guest"

        self.fields["text"].editable = allow_edit
        # sources stay enabled
        self.fields["sources"].editable = allow_edit

    def get_prepared_attachements(self):
        if "text" not in self.changed_data:
            return {}
        b = None
        if self.instance.pk:
            b = self.instance.associated.attachedblobs.filter(
                name="text"
            ).first()
        if not b:
            b = AttachedBlob(
                unique=True, name="text", content=self.instance.associated
            )
        b.blob = self.cleaned_data["text"].encode("utf-8")
        return {
            "attachedblobs": [b]
        }

    def save(self, commit=True):
        if "editable_from" in self.fields:
            self.instance.free_data["editable_from"] = \
                list(self.cleaned_data["editable_from"].values_list(
                    "id", flat=True
                ))

        return super().save(commit)


class RawTextForm(LicenseForm):
    name = forms.CharField()

    def __init__(self, request, source=None, scope=None, **kwargs):
        super().__init__(**kwargs)
        self.initial["text"] = \
            self.instance.associated.attachedblobs.filter(
                name="text"
            ).first()
        self.initial['name'] = self.instance.associated.name
        # sources should not be hashed as they don't affect result
        setattr(self.fields['name'], "hashable", True)
        setattr(self.fields['sources'], "hashable", False)
        setattr(self.fields['license_name'], "hashable", True)
        setattr(self.fields['license_url'], "hashable", True)
