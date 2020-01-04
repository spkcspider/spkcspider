__all__ = ("generate_form", "generate_fields")

import logging
import posixpath
from collections import OrderedDict

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import NON_FIELD_ERRORS
# from django.apps import apps
from django.db.models import Q, QuerySet
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from rdflib import XSD

from spkcspider.apps.spider.abstract_models import BaseContent
from spkcspider.apps.spider.fields import MultipleOpenChoiceField
from spkcspider.apps.spider.models import AssignedContent, ReferrerObject
from spkcspider.apps.spider.queryfilters import loggedin_active_tprotections_q
from spkcspider.apps.spider.widgets import (
    ListWidget, SubSectionStartWidget, SubSectionStopWidget
)
from spkcspider.utils.urls import merge_get_url

from . import registry

# don't spam set objects
_empty_set = frozenset()

logger = logging.getLogger(__name__)


class StartSub(forms.Field):
    widget = SubSectionStartWidget
    hashable = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.widget.label = self.label


class StopSub(forms.Field):
    widget = SubSectionStopWidget
    hashable = False


def generate_fields(layout, prefix="", _base=None, _mainprefix=None):
    if _base is None:
        _base = []
        _mainprefix = prefix
    for i in layout:
        item = i.copy()
        item.setdefault("required", False)
        try:
            key, field = item.pop("key", None), item.pop("field", None)
        except Exception:
            logger.warning("Invalid item (no dict)", i)
            continue
        localize = item.pop("localize", False)
        nonhashable = item.pop("nonhashable", False)
        if not item.get("label"):
            item["label"] = key.replace(_mainprefix, "", 1)

        if localize:
            item["label"] = gettext(item["label"])
            if "help_text" in item:
                item["help_text"] = gettext(item["help_text"])
        if not key or "/" in key:
            logger.warning("Invalid item (no key/contains /)", i)
            continue
        if isinstance(field, list):
            new_prefix = posixpath.join(prefix, key)
            item["required"] = False
            item["initial"] = None
            # by prefixing with _ invalidate prefix for tag recognition
            _base.append((
                "_{}_start".format(new_prefix),
                StartSub(**item)
            ))
            generate_fields(
                field, new_prefix, _base=_base, _mainprefix=_mainprefix
            )
            # by prefixing with _ invalidate prefix for tag recognition
            _base.append((
                "_{}_stop".format(new_prefix),
                StopSub(**item)
            ))
        elif isinstance(field, str):
            new_field = registry.fields.get(field, None)
            if not new_field:
                logger.warning("Invalid field specified: %s", field)
            else:
                new_field = new_field(**item)
                setattr(new_field, "hashable", not nonhashable)
                _base.append((posixpath.join(prefix, key), new_field))
        else:
            logger.warning("Invalid item", i)
    return _base


def generate_form(name, layout):
    _gen_fields = generate_fields(layout, "tag")
    _temp_field = forms.BooleanField(required=False, initial=False)
    setattr(_temp_field, "hashable", True)
    _gen_fields.insert(0, (
        "primary",
        _temp_field
    ))
    _temp_field = MultipleOpenChoiceField(
        required=False, initial=False,
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url")
        )
    )
    setattr(_temp_field, "spkc_datatype", XSD.anyURI)

    _gen_fields.append(("updateable_by", _temp_field))
    _temp_field = MultipleOpenChoiceField(
        required=False, initial=False,
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url to Verifier")
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

        def __init__(
            self, instance, *, request=None, uc=None, initial=None, **kwargs
        ):
            if not initial:
                initial = {}
            self.instance = instance
            _initial = self.encode_initial(initial)
            _initial["primary"] = getattr(instance, "primary", False)
            _initial["verified_by"] = getattr(instance, "verified_by", [])
            super().__init__(
                initial=_initial, **kwargs
            )
            if request:
                travel = \
                    AssignedContent.travel.get_active_for_request(
                        request
                    ).filter(loggedin_active_tprotections_q)
            else:
                # read only, no updates, so disable protections
                travel = AssignedContent.travel.none()
                assert(not self.data and not self.files)

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
                    attrs = getattr(field, "exclude_travel", _empty_set)
                    # must be last
                    if attrs:
                        for i in attrs:
                            q_uc &= ~Q(**{i: travel})
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
            self.instance._cached_references = self.calc_references()[0]
            self.instance.full_clean()
            return self.cleaned_data

        def calc_references(self, use_fields=False):
            _cached_references = []
            attached_to_primary_anchor = False
            items = {}
            if use_fields:
                for name, field in self.fields.items():
                    raw_value = self.initial.get(name, None)
                    value = field.to_python(raw_value)
                    items[name] = (field, value)
            else:
                for name, value in self.cleaned_data.items():
                    items[name] = (self.fields[name], value)
            for key, (field, value) in items.items():
                if key in ("verified_by", "updateable_by", "primary"):
                    continue
                # e.g. anchors
                if isinstance(value, AssignedContent):
                    _cached_references.append(value)
                if (
                    field.__class__.__name__ == "AnchorField" and
                    field.use_default_anchor
                ):
                    if value is None:
                        attached_to_primary_anchor = True

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
            if (
                attached_to_primary_anchor and
                self.instance.associated.usercomponent.primary_anchor
            ):
                _cached_references.append(
                    self.instance.associated.usercomponent.primary_anchor
                )
            # will be saved anyway
            self.instance.associated.attached_to_primary_anchor = \
                attached_to_primary_anchor
            if self.instance.layout.usertag:
                _cached_references.append(
                    self.instance.layout.usertag.associated
                )
            return (
                _cached_references,
                self.instance.associated.attached_to_primary_anchor !=
                attached_to_primary_anchor
            )

        @classmethod
        def encode_initial(cls, initial, prefix="tag", base=None):
            if base is None:
                base = {}
            for i in initial.items():
                if isinstance(i[1], dict):
                    new_prefix = posixpath.join(prefix, i[0])
                    cls.encode_initial(i[1], prefix=new_prefix, base=base)
                else:
                    base[posixpath.join(prefix, i[0])] = i[1]
            return base

        def encode_data(self, cleaned_data, prefix="tag"):
            ret = {}
            for counter, i in enumerate(cleaned_data.items()):
                if not i[0].startswith(prefix):  # unrelated data
                    continue
                selected_dict = ret
                splitted = i[0].split("/")
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
