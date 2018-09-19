from django import forms

from spkcspider.apps.spider.helpers import get_settings_func
from .models import FileFilet, TextFilet


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
                'spider_filets/text.css',
                'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
            ]
        }
        js = [
            'admin/js/vendor/jquery/jquery.min.js',
            'node_modules/trumbowyg/dist/trumbowyg.min.js',
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'spider_filets/text.js'
        ]

    def __init__(self, request, source=None, **kwargs):
        super().__init__(**kwargs)
        self.fields["editable_from"].to_field_name = "name"
        if request.is_owner:
            return

        self.fields["name"].editable = False
        del self.fields["editable_from"]
        allow_edit = False
        if self.instance.editable_from.filter(pk=source.pk).exists():
            if kwargs["request"].is_priv_requester:
                allow_edit = True

        self.fields["text"].editable = allow_edit
