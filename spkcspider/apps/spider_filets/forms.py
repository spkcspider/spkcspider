__all__ = ["FileForm", "TextForm", "RawTextForm"]

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django import forms

from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.fields import SanitizedHtmlField
from .models import FileFilet, TextFilet
from .conf import (
    DEFAULT_LICENSE_FILE, DEFAULT_LICENSE_TEXT, LICENSE_CHOICES
)
from .widgets import LicenseChooserWidget

from spkcspider.apps.spider.fields import (
    OpenChoiceField, MultipleOpenChoiceField
)
from spkcspider.apps.spider.widgets import (
    ListWidget, Select2Widget, TrumbowygWidget
)

_extra = '' if settings.DEBUG else '.min'


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


def _extract_choice(item):
    return (item[0], item[1].get("name", item[0]))


class FileForm(forms.ModelForm):
    request = None

    license_name = OpenChoiceField(
        label=_("License"), help_text=_("Select license"),
        choices=map(_extract_choice, LICENSE_CHOICES.items()),
        widget=LicenseChooserWidget(
            licenses=LICENSE_CHOICES
        )
    )
    sources = MultipleOpenChoiceField(
        required=False, initial=False,
        widget=ListWidget(
            item_label=_("Source")
        )
    )

    class Meta:
        model = FileFilet
        fields = ['file', 'license_name', 'license_url', 'sources']
        widgets = {
            "license_url": forms.URLInput(
                attrs={
                    "style": "width:100%"
                }
            )
        }

    class Media:
        js = [
            'spider_filets/licensechooser.js'
        ]

    def __init__(self, request, uc=None, initial=None, **kwargs):
        if initial is None:
            initial = {}
        if not getattr(kwargs.get("instance", None), "id", None):
            initial.setdefault(
                "license_name", DEFAULT_LICENSE_FILE(uc, request.user)
            )
        super().__init__(initial=initial, **kwargs)
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
        )(self, ret["file"])
        return ret


class TextForm(forms.ModelForm):
    text = SanitizedHtmlField(
        widget=TrumbowygWidget(
            wrapper_attrs={
                "style": "width:60vw"
            }
        ),
        localize=True
    )
    license_name = OpenChoiceField(
        label=_("License"), help_text=_("Select license"),
        choices=map(_extract_choice, LICENSE_CHOICES.items()),
        widget=LicenseChooserWidget(licenses=LICENSE_CHOICES)
    )
    sources = MultipleOpenChoiceField(
        required=False, initial=False,
        widget=ListWidget(
            item_label=_("Source")
        )
    )

    class Meta:
        model = TextFilet
        fields = [
            'text', 'push', 'editable_from',
            'license_name', 'license_url', 'sources'
        ]

        widgets = {
            "editable_from": Select2Widget(
                allow_multiple_selected=True,
                attrs={
                    "style": "min-width: 150px; width:100%"
                }
            ),
            "license_url": forms.URLInput(
                attrs={
                    "style": "width:100%"
                }
            )
        }

    class Media:
        js = [
            'spider_filets/licensechooser.js',
            'spider_filets/description_helper.js'
        ]

    def __init__(self, request, source, scope, initial=None, **kwargs):
        if initial is None:
            initial = {}
        if not getattr(kwargs.get("instance", None), "id", None):
            initial.setdefault(
                "license_name", DEFAULT_LICENSE_TEXT(source, request.user)
            )
        super().__init__(initial=initial, **kwargs)
        if scope in ("add", "update"):
            self.fields["editable_from"].help_text = \
                _(
                    "Allow editing from selected components. "
                    "Requires protection strength >=%s."
                ) % settings.SPIDER_MIN_STRENGTH_EVELATION

            query = models.Q(pk=self.instance.associated.usercomponent.pk)
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


class RawTextForm(forms.ModelForm):
    name = forms.CharField()
    sources = MultipleOpenChoiceField(
        required=False, initial=False
    )

    class Meta:
        model = TextFilet
        fields = ['text', 'license_name', 'license_url', 'sources']

    def __init__(self, request, source=None, scope=None, **kwargs):
        super().__init__(**kwargs)
        self.fields['name'].initial = self.instance.associated.name
        setattr(self.fields['name'], "hashable", True)
        setattr(self.fields['text'], "hashable", True)
        # sources should not be hashed as they don't affect result
        setattr(self.fields['sources'], "hashable", False)
        setattr(self.fields['license_name'], "hashable", True)
        setattr(self.fields['license_url'], "hashable", True)
