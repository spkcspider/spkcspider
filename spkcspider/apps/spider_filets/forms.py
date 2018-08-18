from django import forms
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from spkcspider.apps.spider.helpers import get_filterfunc
from .models import FileFilet, TextFilet


class FileForm(forms.ModelForm):
    user = None

    class Meta:
        model = FileFilet
        fields = ['file', 'name']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['name'].required = False
        if self.instance and self.instance.is_owner(user):
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False

    def clean(self):
        ret = super().clean()
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        func = get_filterfunc("UPLOAD_FILTER_FUNC")
        if not func(ret["file"]):
            raise forms.ValidationError(
                _("%(name)s is not allowed content"),
                code='upload_filter',
                params={'name': ret["file"].name},
            )
        size_diff = ret["file"].size()
        if self.instance.file:
            size_diff -= self.instance.file.size()
        quota = getattr(settings, "FIELDNAME_QUOTA", None)
        if quota:
            quota = getattr(self.user, quota, None)
        if not quota:
            quota = getattr(settings, "DEFAULT_QUOTA_USER", None)
        if quota and self.user.spider_info.used_space + size_diff > quota:
            raise forms.ValidationError(
                _("%(name)s exceeded quota by %(size)s Bytes"),
                code='quota_exceeded',
                params={'name': self.name, 'size': size_diff},
            )
        else:
            self.user.spider_info.used_space += size_diff
            self.user.spider_info.save()
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'non_public_edit']

    def __init__(self, user=None, source=None, **kwargs):
        super().__init__(**kwargs)
        if self.instance and self.instance.is_owner(user):
            return

        self.fields["name"].editable = False
        del self.fields["non_public_edit"]

        self.fields["text"].editable = False

        if self.instance.non_public_edit:
            allow_edit = False
            if source and not source.associated.usercomponent.public:
                allow_edit = True
            elif (
                    not source and
                    not self.instance.associated.usercomponent.public
                 ):
                allow_edit = True

            if allow_edit:
                self.fields["text"].editable = True
