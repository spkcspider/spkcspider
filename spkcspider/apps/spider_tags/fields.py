__all__ = ["installed_fields", "generate_fields"]

import logging
import posixpath
from django import forms
from django.apps import apps
from django.utils.translation import gettext

from spkcspider.apps.spider.helpers import add_by_field
from spkcspider.apps.spider.models import TravelProtection

installed_fields = {}

safe_default_fields = [
    "BooleanField", "CharField", "ChoiceField", "MultipleChoiceField",
    "DateField", "DateTimeField", "DecimalField", "DurationField",
    "EmailField", "FilePathField", "FloatField", "GenericIPAddressField",
    "ModelChoiceField", "ModelMultipleChoiceField", "SlugField", "TimeField",
    "URLField"
]
for i in safe_default_fields:
    installed_fields[i] = getattr(forms, i)


@add_by_field(installed_fields, "__name__")
class TextareaField(forms.CharField):
    widget = forms.Textarea

# extra attributes for fields:
# limit_to_usercomponent = "<fieldname">: limit field name to associated uc
# limit_to_user = "<fieldname">: limit field name to user of associated uc


def localized_choices(obj):
    def func(*, choices=(), **kwargs):
        choices = map(lambda x: (x[0], gettext(x[1])), choices)
        return obj(choices=choices, **kwargs)
    return func


installed_fields["LocalizedChoiceField"] = localized_choices(forms.ChoiceField)
installed_fields["MultipleLocalizedChoiceField"] = \
    localized_choices(forms.MultipleChoiceField)


@add_by_field(installed_fields, "__name__")
class UserContentRefField(forms.ModelChoiceField):
    filter_strength_link = "associated_rel__usercomponent__strength__lte"

    # limit_to_uc: limit to usercomponent, if False to user
    # True is strongly recommended to prevent info leak gadgets
    def __init__(self, modelname, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        if limit_to_uc:
            self.filters_usercomponent = (
                "associated_rel__usercomponent",
                "associated_rel__referenced_by__usercomponent"
            )
        else:
            self.filters_user = ("associated_rel__usercomponent__user",)

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        travel = TravelProtection.objects.get_active()
        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        ).exclude(
            associated_rel__usercomponent__travel_protected__in=travel
        )
        super().__init__(**kwargs)

    def tagdata_from_value(self, obj):
        if obj:
            return obj.pk
        return None

    def label_from_instance(self, obj):
        return str(obj)


@add_by_field(installed_fields, "__name__")
class MultipleUserContentRefField(forms.ModelMultipleChoiceField):
    filter_strength_link = "associated_rel__usercomponent__strength__lte"

    # limit_to_uc: limit to usercomponent, if False to user
    # True is strongly recommended to prevent info leak gadgets
    def __init__(self, modelname, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        if limit_to_uc:
            self.filters_usercomponent = (
                "associated_rel__usercomponent",
                "associated_rel__referenced_by__usercomponent"
            )
        else:
            self.filters_user = ("associated_rel__usercomponent__user",)

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        travel = TravelProtection.objects.get_active()
        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        ).exclude(
            associated_rel__usercomponent__travel_protected__in=travel
        )
        super().__init__(**kwargs)

    def tagdata_from_value(self, query):
        return list(query.values_list(
            'pk', flat=True
        ))

    def label_from_instance(self, obj):
        return str(obj)


@add_by_field(installed_fields, "__name__")
class AnchorField(forms.ModelChoiceField):
    force_embed = True
    filter_strength_link = "usercomponent__strength__lte"

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.models import AssignedContent
        if limit_to_uc:
            self.filters_usercomponent = ("usercomponent",)
        else:
            self.filters_user = ("usercomponent__user",)

        travel = TravelProtection.objects.get_active()
        # can also use Links to anchor as anchor
        kwargs["queryset"] = AssignedContent.objects.filter(
            info__contains="\nanchor\n",
            **kwargs.pop("limit_choices_to", {})
        ).exclude(
            usercomponent__travel_protected__in=travel
        )
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            key = self.to_field_name or 'pk'
            value = self.queryset.get(**{key: value}).content
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'], code='invalid_choice'
            )
        return value

    def tagdata_from_value(self, obj):
        if obj:
            return obj.associated.id
        return None

    def label_from_instance(self, obj):
        return str(obj.content)


def generate_fields(layout, prefix="", _base=None, _mainprefix=None):
    if not _base:
        _base = []
        _mainprefix = prefix
    for i in layout:
        item = i.copy()
        key, field = item.pop("key", None), item.pop("field", None)
        localize = item.pop("localize", False)
        nonhashable = item.pop("nonhashable", False)
        if "label" not in item:
            item["label"] = key.replace(_mainprefix, "", 1)

        if localize:
            item["label"] = gettext(item["label"])
            if "help_text" in item:
                item["help_text"] = gettext(item["help_text"])
        # readd prefix to label:
        item["label"] = "".join(
                [
                    # remove mainprefix
                    *prefix.replace(
                        _mainprefix, "", 1
                    ).replace("/", " > "),  # beautify /
                    item["label"],
                ]
            )
        if not key or "/" in key:
            logging.warning("Invalid item (no key/contains /)", i)
            continue
        if isinstance(field, list):
            new_prefix = posixpath.join(prefix, key)
            generate_fields(
                field, new_prefix, _base=_base, _mainprefix=_mainprefix
            )
        elif isinstance(field, str):
            new_field = installed_fields.get(field, None)
            if not new_field:
                logging.warning("Invalid field specified: %s", field)
            else:
                new_field = new_field(**item)
                setattr(new_field, "hashable", not nonhashable)
                _base.append((posixpath.join(prefix, key), new_field))
        else:
            logging.warning("Invalid item", i)
    return _base
