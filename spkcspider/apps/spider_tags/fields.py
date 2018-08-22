__all__ = ["valid_fields", "generate_fields"]

import logging
from django import forms
from django.apps import apps

valid_fields = {}

safe_default_fields = [
    "BooleanField", "CharField", "ChoiceField", "MultipleChoiceField",
    "DateField", "DateTimeField", "DecimalField", "DurationField",
    "EmailField", "FilePathField", "FloatField", "GenericIPAddressField",
    "ModelChoiceField", "ModelMultipleChoiceField", "SlugField", "TimeField",
    "URLField"
]
for i in safe_default_fields:
    valid_fields[i] = getattr(forms, i)


class TextareaField(forms.CharField):
    widget = forms.Textarea
valid_fields["TextareaField"] = TextareaField  # noqa: E305

# extra attributes for fields:
# limit_to_usercomponent = "<fieldname">: limit field name to associated uc
# limit_to_user = "<fieldname">: limit field name to user of associated uc


class UserContentRefField(forms.ModelChoiceField):
    embed_content = None

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, modelname, limit_to_uc=True, embed=False, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        self.embed_content = embed
        if limit_to_uc:
            self.limit_to_usercomponent = "associated_rel__usercomponent"
        else:
            self.limit_to_user = "associated_rel__usercomponent__user"

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)
valid_fields["UserContentRefField"] = UserContentRefField  # noqa: E305


class UserContentMultipleRefField(forms.ModelMultipleChoiceField):
    embed_content = None

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, modelname, limit_to_uc=True, embed=False, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        self.embed_content = embed
        if limit_to_uc:
            self.limit_to_usercomponent = "associated_rel__usercomponent"
        else:
            self.limit_to_user = "associated_rel__usercomponent__user"

        model = apps.get_model(
            modelname
        )
        if not isinstance(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)
valid_fields["UserContentMultipleRefField"] = UserContentMultipleRefField  # noqa: E305, E501


def generate_fields(layout, prefix="", _base=None, _mainprefix=None):
    if not _base:
        _base = []
        _mainprefix = prefix
    for i in layout:
        item = i.copy()
        key, field = item.pop("key", None), item.pop("field", None)
        if "label" not in item:
            item["label"] = key.replace(_mainprefix, "", 1).replace(":", ": ")
        else:
            item["label"] = ": ".join(
                [
                    prefix.replace(
                        _mainprefix, "", 1
                    ).replace(
                        ":", ": "
                    ),
                    item["label"]
                ]
            )
        if not key or ":" in key:
            logging.warning("Invalid item (no key/contains :)", i)
            continue
        if isinstance(field, list):
            new_prefix = "{}:{}".format(prefix, key)
            generate_fields(
                field, new_prefix, _base=_base, _mainprefix=_mainprefix
            )
        elif isinstance(field, str):
            new_field = valid_fields.get(field)
            if not new_field:
                logging.warning("Invalid field specified: %s", field)
            else:
                _base.append(("{}:{}".format(prefix, key), new_field(**item)))
        else:
            logging.warning("Invalid item", i)
    return _base
