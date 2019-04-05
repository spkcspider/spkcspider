__all__ = ["FileForm", "TextForm", "RawTextForm"]

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django import forms

from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.fields import SanitizedHtmlField
from .models import FileFilet, TextFilet
from .conf import (
    DEFAULT_LICENSE_FILE, LICENSE_CHOICES_FILE,
    DEFAULT_LICENSE_TEXT, LICENSE_CHOICES_TEXT
)
from .widgets import LicenseChooserWidget

from spkcspider.apps.spider.fields import OpenChoiceField
from spkcspider.apps.spider.widgets import OpenChoiceWidget

_extra = '' if settings.DEBUG else '.min'


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


def _extract_choice(item):
    return (item[0], item[1][0])


class FileForm(forms.ModelForm):
    license_name = forms.ChoiceField(
        label=_("License"), help_text=_("Select license"),
        choices=map(_extract_choice, LICENSE_CHOICES_FILE.items()),
        widget=LicenseChooserWidget(licenses=LICENSE_CHOICES_FILE)
    )
    sources = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
        )
    )

    class Meta:
        model = FileFilet
        fields = ['file', 'license_name', 'license', 'sources']
        widgets = {
            # "sources": ListWidget(item_label=_("Source"))
        }

    class Media:
        js = [
            'spider_filets/licensechooser.js'
        ]

    def __init__(self, request, uc=None, initial=None, **kwargs):
        if initial is None:
            initial = {}
        initial.setdefault(
            "license_name", DEFAULT_LICENSE_FILE(uc, request.user)
        )
        super().__init__(initial=initial, **kwargs)
        setattr(self.fields['file'], "hashable", True)
        # sources should not be hashed as they don't affect result
        setattr(self.fields['sources'], "hashable", False)
        raw_value = self.initial.get("license_name", "other")
        value = self.fields['license_name'].to_python(raw_value)
        if value == "other":
            setattr(self.fields['license'], "hashable", True)
        else:
            setattr(self.fields['license_name'], "hashable", True)
        if request.user.is_superuser:
            # no upload limit
            pass
        elif request.user.is_staff:
            self.fields["file"].max_length = getattr(
                settings, "MAX_FILE_SIZE_STAFF", None
            )
        else:
            self.fields["file"].max_length = getattr(
                settings, "MAX_FILE_SIZE", None
            )
        if request.is_owner:
            # self.user = request.user
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False
        self.fields["license_name"].editable = False
        self.fields["license"].editable = False
        # sources stay enabled
        self.fields["sources"].editable = True

    def clean(self):
        ret = super().clean()
        if "file" not in ret:
            return ret
        # has to raise ValidationError
        get_settings_func(
            "UPLOAD_FILTER_FUNC",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )(ret["file"])
        return ret


class TextForm(forms.ModelForm):
    text = SanitizedHtmlField()
    license_name = forms.ChoiceField(
        label=_("License"), help_text=_("Select license"),
        choices=map(_extract_choice, LICENSE_CHOICES_TEXT.items()),
        widget=LicenseChooserWidget(licenses=LICENSE_CHOICES_TEXT)
    )
    sources = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
        )
    )

    class Meta:
        model = TextFilet
        fields = [
            'text', 'push', 'editable_from',
            'license_name', 'license', 'sources'
        ]

        # widgets = {
        #    "editable_from": forms.CheckboxSelectMultiple(),
        #    "sources": ListWidget(
        #        item_label=_("Source")
        #    )
        # }

    class Media:
        js = [
            'spider_filets/licensechooser.js'
        ]

    def __init__(self, request, source, scope, initial=None, **kwargs):
        if initial is None:
            initial = {}
        initial.setdefault(
            "license_name", DEFAULT_LICENSE_TEXT(source, request.user)
        )
        super().__init__(initial=initial, **kwargs)
        if scope in ("add", "update"):
            self.fields["editable_from"].help_text = \
                _(
                    "Allow editing from selected components. "
                    "Requires protection strength >=%s."
                ) % settings.MIN_STRENGTH_EVELATION

            query = models.Q(pk=self.instance.associated.usercomponent.pk)
            if scope == "update":
                query |= models.Q(
                    contents__references=self.instance.associated
                )
            query &= models.Q(strength__gte=settings.MIN_STRENGTH_EVELATION)
            query &= models.Q(strength__lt=9)
            self.fields["editable_from"].queryset = \
                self.fields["editable_from"].queryset.filter(query).distinct()
            return

        del self.fields["editable_from"]
        del self.fields["preview_words"]
        del self.fields["push"]

        allow_edit = False
        if scope == "update_guest":
            allow_edit = True

        self.fields["text"].disabled = not allow_edit


class RawTextForm(forms.ModelForm):
    name = forms.CharField()
    sources = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
        )
    )

    class Meta:
        model = TextFilet
        fields = ['text', 'license_name', 'license', 'sources']

    def __init__(self, request, source=None, scope=None, **kwargs):
        super().__init__(**kwargs)
        self.fields['name'].initial = self.instance.associated.name
        setattr(self.fields['name'], "hashable", True)
        setattr(self.fields['text'], "hashable", True)
        # sources should not be hashed as they don't affect result
        setattr(self.fields['sources'], "hashable", False)
        raw_value = self.initial.get("license_name", "other")
        value = self.fields['license_name'].to_python(raw_value)
        if value == "other":
            setattr(self.fields['license'], "hashable", True)
        else:
            setattr(self.fields['license_name'], "hashable", True)
            self.fields['license'].initial = \
                LICENSE_CHOICES_TEXT[value][1]
