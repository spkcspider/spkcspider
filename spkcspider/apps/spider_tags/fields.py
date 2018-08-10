__all__ = ["valid_fields", "generate_fields"]

import logging
from django import forms
from django.conf import settings
from django.apps import apps

valid_fields = {}

safe_default_fields = [
    "BooleanField", "CharField", "ChoiceField", "DateField", "DateTimeField",
    "DecimalField", "DurationField", "EmailField", "FilePathField",
    "FloatField", "GenericIPAddressField", "Select", "SelectMultiple",
    "SlugField", "TimeField", "URLField"
]
for i in safe_default_fields:
    valid_fields[i] = getattr(forms, i)


class TextareaField(forms.CharField):
    widget = forms.Textarea
valid_fields["TextareaField"] = TextareaField  # noqa: E305

# extra attributes for fields:
# limit_to_usercomponent = "<fieldname">: limit field name to associated uc
# limit_to_user = "<fieldname">: limit field name to user of associated uc


class LayoutRefField(forms.ModelChoiceField):
    limit_to_usercomponent = "associated_rel__usercomponent"

    def __init__(self, valid_layouts, **kwargs):
        kwargs["queryset"] = apps.get_model(
            "spider_tags.SpiderTag"
        ).objects.all()
        if isinstance(valid_layouts, list):
            kwargs["queryset"] = kwargs["queryset"].filter(
                layout__name__in=valid_layouts
            )
        kwargs.pop("limit_choices_to", None)
        super().__init__(**kwargs)
valid_fields["LayoutRefField"] = LayoutRefField  # noqa: E305


if "spkcspider.apps.spider_filets" in settings.INSTALLED_APPS:
    class FileRefField(forms.ModelChoiceField):
        limit_to_usercomponent = "associated_rel__usercomponent"

        def __init__(self, **kwargs):
            kwargs["queryset"] = apps.get_model(
                "spider_filets.FileFilet"
            ).objects.all()
            kwargs.pop("limit_choices_to", None)
            super().___init__(**kwargs)
    valid_fields["FileFiletField"] = FileRefField


def generate_fields(layout, prefix="", base=None):
    if not base:
        base = []
    for i in layout:
        item = i.copy()
        key, field = item.pop("key", None), item.pop("field", None)
        if not key or ":" in key:
            logging.warning("Invalid item (no key/contains :)", i)
            continue
        if isinstance(field, list):
            new_prefix = "{}:{}".format(prefix, key)
            generate_fields(field, new_prefix, base=base)
        elif isinstance(field, str):
            new_field = valid_fields.get(field)
            if not new_field:
                logging.warning("Invalid field specified: %s", field)
            else:
                base.append(("{}:{}".format(prefix, key), new_field(**item)))
        else:
            logging.warning("Invalid item", i)
    return base
