__all__ = ["FileForm", "TextForm", "RawTextForm"]


import bleach
from bleach import sanitizer

from django import forms

from spkcspider.apps.spider.helpers import get_settings_func
from .models import FileFilet, TextFilet

tags = sanitizer.ALLOWED_TAGS + ['img', 'p', 'br', 'sub', 'sup']
protocols = sanitizer.ALLOWED_PROTOCOLS + ['data']


class FakeList(object):
    def __contains__(self, value):
        return True


styles = FakeList()
svg_props = FakeList()


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


class FileForm(forms.ModelForm):
    user = None

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

    def clean(self):
        ret = super().clean()
        if "file" not in ret:
            return ret
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        get_settings_func(
            "UPLOAD_FILTER_FUNC",
            "spkcspider.apps.spider.functions.validate_file"
        )(ret["file"])
        size_diff = ret["file"].size
        if self.instance.file:
            size_diff -= self.instance.file.size
        self.user.spider_info.update_quota(size_diff)
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'editable_from']

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
            'admin/js/vendor/jquery/jquery.min.js',
            'node_modules/trumbowyg/dist/trumbowyg.min.js',
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
            'spider_filets/text.js'
        ]

    def __init__(self, request, source=None, **kwargs):
        super().__init__(**kwargs)
        self.fields["editable_from"].to_field_name = "name"
        if request.is_owner:
            self.fields["editable_from"].queryset = \
                self.fields["editable_from"].queryset.filter(
                    user=request.user
                ).exclude(name__in=("index", "fake_index"))
            return

        del self.fields["editable_from"]
        allow_edit = False
        if self.instance.editable_from.filter(pk=source.pk).exists():
            if request.is_priv_requester:
                allow_edit = True

        self.fields["text"].editable = allow_edit

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

    def __init__(self, request, source=None, **kwargs):
        super().__init__(**kwargs)
