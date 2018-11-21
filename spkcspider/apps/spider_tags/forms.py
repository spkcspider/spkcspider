__all__ = [
    "TagLayoutForm", "SpiderTagForm", "generate_form",
]

import posixpath
from collections import OrderedDict
# from django.utils.translation import gettext_lazy as _
from django import forms

# from django.apps import apps
from django.db.models import Q
from django.db import models
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _

from .fields import generate_fields
from .models import TagLayout, SpiderTag


class TagLayoutForm(forms.ModelForm):
    class Meta:
        model = TagLayout
        fields = ["name", "layout", "default_verifiers"]

    def __init__(self, uc=None, **kwargs):
        if "instance" not in kwargs:
            kwargs["instance"] = self._meta.model(usertag=uc)
        super().__init__(**kwargs)


class SpiderTagForm(forms.ModelForm):
    class Meta:
        model = SpiderTag
        fields = ["layout"]

    def __init__(self, user=None, **kwargs):
        super().__init__(**kwargs)
        index = user.usercomponent_set.get(name="index")
        self.fields["layout"].queryset = self.fields["layout"].queryset.filter(
            Q(usertag__isnull=True) |
            Q(usertag__associated_rel__usercomponent=index)
        ).order_by("name")


def generate_form(name, layout):
    _gen_fields = generate_fields(layout, "tag")
    _gen_fields.insert(0, (
        "primary",
        forms.BooleanField(required=False, initial=False)
    ))

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

        def __init__(self, *, uc=None, initial=None, instance=None, **kwargs):
            if not initial:
                initial = {}
            self.instance = instance
            _initial = self.encode_initial(initial)
            _initial["primary"] = getattr(instance, "primary", False)
            super().__init__(
                initial=_initial, **kwargs
            )
            for field in self.fields.values():
                if hasattr(field, "queryset"):
                    filters = {}
                    attr = getattr(field, "strength_link_field", None)
                    if attr:
                        filters[attr] = uc.strength
                    attr = getattr(field, "limit_to_usercomponent", None)
                    if attr:
                        filters[attr] = uc
                    attr = getattr(field, "limit_to_user", None)
                    if attr:
                        filters[attr] = uc.user
                    field.queryset = field.queryset.filter(**filters)

        def clean(self):
            if self.instance:
                self.instance.full_clean()
            return super().clean()

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

        @staticmethod
        def encode_data(cleaned_data, prefix="tag"):
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
                if isinstance(i[1], models.Model):
                    selected_dict[splitted[-1]] = i[1].pk
                elif isinstance(i[1], models.QuerySet):
                    selected_dict[splitted[-1]] = list(i[1].values_list(
                        'id', flat=True
                    ))
                else:
                    selected_dict[splitted[-1]] = i[1]
            return ret

        def save_m2m(self):
            pass

        def save(self, commit=True):
            if self.instance:
                self.instance.primary = self.cleaned_data["primary"]
                self.instance.tagdata = self.encode_data(self.cleaned_data)
                if commit:
                    self.instance.save()

            return self.instance

    return _form
