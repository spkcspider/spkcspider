from django import forms

from .models import FileFilet, TextFilet


class FileForm(forms.ModelForm):
    class Meta:
        model = FileFilet
        fields = ['file', 'name']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        if self.instance and self.instance.is_owner(user):
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False

    def clean(self):
        ret = super().clean()
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'edit_allowed']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.is_owner(user):
            return

        self.fields["name"].editable = False
        del self.fields["edit_allowed"]

        if not user.is_authenticated or \
           not self.instance.edit_allowed.filter(pk=user.pk).exists():
            self.fields["text"].editable = False
