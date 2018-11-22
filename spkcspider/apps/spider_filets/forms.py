__all__ = ["FileForm", "TextForm", "RawTextForm"]


import bleach
from bleach import sanitizer

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django import forms

from spkcspider.apps.spider.constants.static import index_names
from spkcspider.apps.spider.helpers import get_settings_func
from .models import FileFilet, TextFilet

tags = sanitizer.ALLOWED_TAGS + [
    'img', 'p', 'br', 'sub', 'sup', 'h1', 'h2', 'h3', 'h4'
]
protocols = sanitizer.ALLOWED_PROTOCOLS + ['data']


class FakeList(object):
    def __contains__(self, value):
        return True


styles = FakeList()
svg_props = FakeList()
_extra = '' if settings.DEBUG else '.min'


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


class FileForm(forms.ModelForm):
    user = None
    MAX_FILE_SIZE = forms.CharField(
        disabled=True, widget=forms.HiddenInput(), required=False
    )

    class Meta:
        model = FileFilet
        fields = ['file', 'name']

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.fields['name'].required = False
        if request.is_owner:
            self.user = request.user
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False
        if request.user.is_staff or request.user.is_superuser:
            self.fields["MAX_FILE_SIZE"].initial = getattr(
                settings, "MAX_FILE_SIZE", None
            )
        else:
            self.fields["MAX_FILE_SIZE"].initial = getattr(
                settings, "MAX_FILE_SIZE_STAFF", None
            )
        if not self.fields["MAX_FILE_SIZE"].initial:
            del self.fields["MAX_FILE_SIZE"]

    def clean(self):
        ret = super().clean()
        if "file" not in ret:
            return ret
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        # has to raise ValidationError
        get_settings_func(
            "UPLOAD_FILTER_FUNC",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )(ret["file"])
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'editable_from', 'preview_words']

        widgets = {
            "editable_from": forms.CheckboxSelectMultiple()
        }

    class Media:
        css = {
            'all': [
                'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                'spider_base/trumbowyg.css',
                # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
            ]
        }
        js = [
            'admin/js/vendor/jquery/jquery%s.js' % _extra,
            'node_modules/trumbowyg/dist/trumbowyg%s.js' % _extra,
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
            'spider_filets/text.js'
        ]

    def __init__(self, request, source, scope, **kwargs):
        super().__init__(**kwargs)
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
            query &= ~models.Q(name__in=index_names)
            self.fields["editable_from"].queryset = \
                self.fields["editable_from"].queryset.filter(query).distinct()
            return

        del self.fields["editable_from"]
        del self.fields["preview_words"]
        del self.fields["name"]

        allow_edit = False
        if scope == "update_user":
            allow_edit = True

        self.fields["text"].disabled = not allow_edit

    def clean_text(self):
        return bleach.clean(
            self.cleaned_data['text'],
            tags=tags,
            attributes=check_attrs_func,
            protocols=protocols,
            styles=styles,
        )


class RawTextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name']

    def __init__(self, request, source=None, scope=None, **kwargs):
        super().__init__(**kwargs)
