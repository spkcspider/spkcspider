from django import forms

from .models import FileFilet, TextFilet


class FileForm(forms.ModelForm):
    class Meta:
        model = FileFilet
        fields = ['file', 'name']


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and \
           user != self.instance.associated.usercomponent.user:
            if user not in self.instance.edit_allowed:
                self.fields["text"].editable = False
                self.fields["name"].editable = False
