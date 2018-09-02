from django import forms
from django.utils.translation import gettext_lazy as _
from django.conf import settings

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
        func = get_settings_func(
            "UPLOAD_FILTER_FUNC",
            "spkcspider.apps.spider.helpers.ALLOW_ALL_FILTER_FUNC"
        )
        if not func(ret["file"]):
            raise forms.ValidationError(
                _("%(name)s is not allowed content"),
                code='upload_filter',
                params={'name': ret["file"].name},
            )
        size_diff = ret["file"].size
        if self.instance.file:
            size_diff -= self.instance.file.size
        quota = getattr(settings, "FIELDNAME_QUOTA", None)
        if quota:
            quota = getattr(self.user, quota, None)
        if not quota:
            quota = getattr(settings, "DEFAULT_QUOTA_USER", None)
        if quota and self.user.spider_info.used_space + size_diff > quota:
            raise forms.ValidationError(
                _("%(name)s exceeded quota by %(size)s Bytes"),
                code='quota_exceeded',
                params={'name': ret["name"], 'size': size_diff},
            )
        else:
            self.user.spider_info.used_space += size_diff
            self.user.spider_info.save()
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'editable_from']

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
