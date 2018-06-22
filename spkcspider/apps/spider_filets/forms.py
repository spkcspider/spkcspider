from django import forms

from .models import FileFilet, TextFilet


class FileForm(forms.ModelForm):
    class Meta:
        model = FileFilet
        fields = ['file', 'name']


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'edit_allowed']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.is_owner(user):
            return
        if not user.is_authenticated or \
           not self.instance.edit_allowed.filter(pk=user.pk).exists():
            self.fields["text"].editable = False
            self.fields["name"].editable = False
            self.fields["edit_allowed"].disabled = True
            self.fields["edit_allowed"].widget = forms.HiddenInput()
