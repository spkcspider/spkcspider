
from django import forms
from django.apps import apps
from django.utils.translation import gettext, gettext_lazy
from spkcspider.utils.fields import add_by_field

from . import registry

safe_default_fields = [
    "BooleanField", "CharField", "ChoiceField", "MultipleChoiceField",
    "DateField", "DateTimeField", "DecimalField", "DurationField",
    "EmailField", "FilePathField", "FloatField", "GenericIPAddressField",
    "ModelChoiceField", "ModelMultipleChoiceField", "SlugField", "TimeField",
    "URLField"
]
for i in safe_default_fields:
    registry.fields[i] = getattr(forms, i)


@add_by_field(registry.fields, "__name__")
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


registry.fields["LocalizedChoiceField"] = localized_choices(forms.ChoiceField)
registry.fields["MultipleLocalizedChoiceField"] = \
    localized_choices(forms.MultipleChoiceField)


@add_by_field(registry.fields, "__name__")
class UserContentRefField(forms.ModelChoiceField):
    filter_strength_link = "associated__usercomponent__strength__lte"
    exclude_travel = (
        "associated__usercomponent__travel_protected__in",
        "associated__travel_protected__in",
    )

    # limit_to_uc: limit to usercomponent, if False to user
    # True is strongly recommended to prevent info leak gadgets
    def __init__(self, modelname, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.abstract_models import BaseContent
        if limit_to_uc:
            self.filters_usercomponent = (
                "associated__usercomponent",
                "associated__referenced_by__usercomponent"
            )
        else:
            self.filters_user = ("associated__usercomponent__user",)

        model = apps.get_model(modelname)
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)

    def tagdata_from_value(self, obj):
        if obj:
            return obj.pk
        return None

    def label_from_instance(self, obj):
        return str(obj)


@add_by_field(registry.fields, "__name__")
class MultipleUserContentRefField(forms.ModelMultipleChoiceField):
    filter_strength_link = "associated__usercomponent__strength__lte"
    exclude_travel = (
        "associated__usercomponent__travel_protected__in",
        "associated__travel_protected__in",
    )

    # limit_to_uc: limit to usercomponent, if False to user
    # True is strongly recommended to prevent info leak gadgets
    def __init__(self, modelname, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        if limit_to_uc:
            self.filters_usercomponent = (
                "associated__usercomponent",
                "associated__referenced_by__usercomponent"
            )
        else:
            self.filters_user = ("associated__usercomponent__user",)

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)

    def tagdata_from_value(self, query):
        return list(query.values_list(
            'pk', flat=True
        ))

    def label_from_instance(self, obj):
        return str(obj)


@add_by_field(registry.fields, "__name__")
class AnchorField(forms.ModelChoiceField):
    spkc_use_uriref = True
    use_default_anchor = None
    filter_strength_link = "usercomponent__strength__lte"
    exclude_travel = (
        "associated__usercomponent__travel_protected__in",
        "associated__travel_protected__in",
    )

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(
        self, use_default_anchor=True, limit_to_uc=True, **kwargs
    ):
        from spkcspider.apps.spider.models import AssignedContent
        _ = gettext_lazy
        if limit_to_uc:
            self.filters_usercomponent = ("usercomponent",)
        else:
            self.filters_user = ("usercomponent__user",)
        self.use_default_anchor = use_default_anchor
        if use_default_anchor:
            kwargs.setdefault("required", False)
        if use_default_anchor and not kwargs.get("empty_label", None):
            kwargs["empty_label"] = _("(Use default anchor)")

        # can also use Links to anchor as anchor
        kwargs["queryset"] = AssignedContent.objects.filter(
            info__contains="\x1eanchor\x1e",
            **kwargs.pop("limit_choices_to", {})
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
            return obj.associated_id
        return None

    def label_from_instance(self, obj):
        return str(obj.content)
