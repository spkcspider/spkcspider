__all__ = [
    "TagLayoutForm", "TagLayoutAdminForm", "SpiderTagForm",
]

from django import forms
# from django.utils.translation import gettext_lazy as _
from django.conf import settings
# from django.apps import apps
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from spkcspider.apps.spider.fields import JsonField, MultipleOpenChoiceField
from spkcspider.apps.spider.models import (
    ReferrerObject
)
from spkcspider.apps.spider.widgets import ListWidget
from spkcspider.utils.urls import merge_get_url

from . import registry
from .models import SpiderTag, TagLayout
from .widgets import SchemeWidget

_extra = '' if settings.DEBUG else '.min'


class TagLayoutForm(forms.ModelForm):
    layout = JsonField(
        widget=SchemeWidget(registry.fields.keys())
    )
    default_verifiers = MultipleOpenChoiceField(
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url to Verifier")
        ), required=False
    )

    class Meta:
        model = TagLayout
        fields = ["name", "unique", "layout", "default_verifiers"]

    usertaglayout = None

    def __init__(self, usertaglayout, **kwargs):
        self.usertaglayout = usertaglayout
        super().__init__(**kwargs)

    def _save_m2m(self):
        self.instance.usertag = self.usertaglayout.associated
        self.instance.name = self.usertaglayout.associated.name
        self.instance.description = self.usertaglayout.associated.description
        self.instance.save()
        self.instance.usertag.refresh_from_db()
        return super()._save_m2m()

    def clean_default_verifiers(self):
        values = self.cleaned_data["default_verifiers"]
        if not isinstance(values, list):
            raise forms.ValidationError(
                _("Invalid format"),
                code='invalid_format'
            )
        values = list(map(merge_get_url, values))
        return values

    def clean(self):
        self.usertaglayout.full_clean()
        return super().clean()

    def save(self, commit=True):
        if commit:
            self.usertaglayout.save()
            self._save_m2m()
        else:
            self.save_m2m = self._save_m2m
        return self.usertaglayout


class TagLayoutAdminForm(forms.ModelForm):
    layout = JsonField(
        widget=SchemeWidget(registry.fields.keys())
    )
    default_verifiers = MultipleOpenChoiceField(
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url to Verifier")
        ), required=False
    )

    class Meta:
        model = TagLayout
        fields = ["name", "unique", "layout", "default_verifiers", "usertag"]

    class Media:
        css = {
            'all': [
                'node_modules/@fortawesome/fontawesome-free/css/all.min.css'
            ]
        }

    def clean_default_verifiers(self):
        values = self.cleaned_data["default_verifiers"]
        if not isinstance(values, list):
            raise forms.ValidationError(
                _("Invalid format"),
                code='invalid_format'
            )
        values = list(map(merge_get_url, values))
        return values


class SpiderTagForm(forms.ModelForm):
    updateable_by = MultipleOpenChoiceField(
        required=False, initial=False,
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url")
        )
    )
    layout = forms.ModelChoiceField(
        queryset=TagLayout.objects.none(),
        to_field_name="name"
    )

    class Meta:
        model = SpiderTag
        fields = ["layout", "updateable_by"]

    def __init__(self, user=None, **kwargs):
        super().__init__(**kwargs)
        index = user.usercomponent_set.get(name="index")
        self.fields["layout"].queryset = TagLayout.objects.filter(
            Q(usertag__isnull=True) |
            Q(usertag__usercomponent=index)
        ).order_by("name")

    def clean_updateable_by(self):
        values = self.cleaned_data["updateable_by"]
        values = set(map(merge_get_url, values))
        existing = ReferrerObject.objects.filter(
            url__in=values
        ).values_list("url", flat=True)
        for url in values.difference(existing):
            # extra validation
            ReferrerObject.objects.get_or_create(
                url=url
            )
        return ReferrerObject.objects.filter(
            url__in=values
        )
