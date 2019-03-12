__all__ = [
    "TagLayoutForm", "SpiderTagForm", "generate_form",
]

import posixpath
from collections import OrderedDict
# from django.utils.translation import gettext_lazy as _
from django import forms

# from django.apps import apps
from django.db.models import Q, QuerySet
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _

from rdflib import XSD

from .fields import generate_fields
from .models import TagLayout, SpiderTag

from spkcspider.apps.spider.fields import OpenChoiceField
from spkcspider.apps.spider.widgets import OpenChoiceWidget
from spkcspider.apps.spider.helpers import merge_get_url
from spkcspider.apps.spider.models import (
    AssignedContent, ReferrerObject
)
from spkcspider.apps.spider.contents import BaseContent


# don't spam set objects
_empty_set = frozenset()


class TagLayoutForm(forms.ModelForm):
    class Meta:
        model = TagLayout
        fields = ["name", "unique", "layout", "default_verifiers"]

    usertag = None

    def _save_m2m(self):
        self.instance.usertag = self.usertag
        self.instance.save()
        self.instance.usertag.refresh_from_db()
        return super()._save_m2m()

    def save(self, commit=True):
        self.usertag = self.instance.usertag
        if commit:
            self.usertag.save()
            self._save_m2m()
        else:
            self.save_m2m = self._save_m2m
        return self.usertag


class SpiderTagForm(forms.ModelForm):
    updateable_by = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
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
            Q(usertag__associated_rel__usercomponent=index)
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


def generate_form(name, layout):
    _gen_fields = generate_fields(layout, "tag")
    _temp_field = forms.BooleanField(required=False, initial=False)
    setattr(_temp_field, "hashable", True)
    _gen_fields.insert(0, (
        "primary",
        _temp_field
    ))
    _temp_field = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
        )
    )
    setattr(_temp_field, "spkc_datatype", XSD.anyURI)

    _gen_fields.append(("updateable_by", _temp_field))
    _temp_field = OpenChoiceField(
        required=False, initial=False,
        widget=OpenChoiceWidget(
            attrs={
                "style": "min-width: 300px; width:100%"
            }
        )
    )
    setattr(_temp_field, "spkc_datatype", XSD.anyURI)
    _gen_fields.append(("verified_by", _temp_field))

    class _form(forms.BaseForm):
        __name__ = name
        declared_fields = OrderedDict(_gen_fields)
        base_fields = declared_fields
        # used in models
        layout_generating_form = True

        class Meta:
            error_messages = {
                NON_FIELD_ERRORS: {
                    'unique_together': _(
                        'Primary layout for "%s" exists already'
                    ) % name
                }
            }

        def __init__(self, instance, *, uc=None, initial=None, **kwargs):
            if not initial:
                initial = {}
            self.instance = instance
            _initial = self.encode_initial(initial)
            _initial["primary"] = getattr(instance, "primary", False)
            _initial["verified_by"] = getattr(instance, "verified_by", [])
            super().__init__(
                initial=_initial, **kwargs
            )

            for field in self.fields.values():
                if hasattr(field, "queryset"):
                    filters = {}
                    q_user = Q()
                    q_uc = Q()
                    # can also contain __lte or so
                    attr = getattr(field, "filter_strength_link", None)
                    if attr:
                        filters[attr] = uc.strength
                    attrs = getattr(field, "filters_user", _empty_set)
                    if attrs:
                        for i in attrs:
                            q_user |= Q(**{i: uc.user})
                    attrs = getattr(field, "filters_usercomponent", _empty_set)
                    if attrs:
                        for i in attrs:
                            q_uc |= Q(**{i: uc})
                    field.queryset = field.queryset.filter(
                        q_user, q_uc, **filters
                    )

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

        def clean(self):
            super().clean()

            _cached_references = []
            for key, value in self.cleaned_data.items():
                if key in ("verified_by", "updateable_by", "primary"):
                    continue
                # e.g. anchors
                if isinstance(value, AssignedContent):
                    _cached_references.append(value)

                if issubclass(type(value), BaseContent):
                    _cached_references.append(value.associated)

                # e.g. anchors
                if isinstance(value, QuerySet):
                    if issubclass(value.model, AssignedContent):
                        _cached_references += list(value)

                    if issubclass(value.model, BaseContent):
                        _cached_references += list(
                            AssignedContent.objects.filter(
                                object_id__in=value.values_list(
                                    "id", flat=True
                                ),
                                content_type=ContentType.objects.get_for_model(
                                    value.model
                                )
                            )
                        )
            self.instance._cached_references = _cached_references
            self.instance.full_clean()
            return self.cleaned_data

        @classmethod
        def encode_initial(cls, initial, prefix="tag", base=None):
            if not base:
                base = {}
            for i in initial.items():
                if isinstance(i[1], dict):
                    new_prefix = posixpath.join(prefix, i[0])
                    cls.encode_initial(i[i], prefix=new_prefix, base=base)
                else:
                    base[posixpath.join(prefix, i[0])] = i[1]
            return base

        def encode_data(self, cleaned_data, prefix="tag"):
            ret = {}
            for counter, i in enumerate(cleaned_data.items()):
                selected_dict = ret
                splitted = i[0].split("/")
                if splitted[0] != prefix:  # unrelated data
                    continue
                # last key is item key, first is "tag"
                for key in splitted[1:-1]:
                    if key not in selected_dict:
                        selected_dict[key] = {}
                    selected_dict = selected_dict[key]
                if hasattr(self.fields[i[0]], "tagdata_from_value"):
                    selected_dict[splitted[-1]] = \
                        self.fields[i[0]].tagdata_from_value(i[1])
                else:
                    selected_dict[splitted[-1]] = i[1]
            return ret

        def save_m2m(self):
            pass

        def save(self, commit=True):
            self.instance.primary = self.cleaned_data["primary"]
            # self.instance.verified_by = self.cleaned_data["verified_by"]
            # self.instance.updateable_by = self.cleaned_data["updateable_by"]
            self.instance.tagdata = self.encode_data(self.cleaned_data)
            if commit:
                self.instance.save()

            return self.instance

    return _form
