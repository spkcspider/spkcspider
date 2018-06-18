from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import PublicKey


class KeyForm(forms.ModelForm):
    usercomponent = None

    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def __init__(self, *args, uc=None, **kwargs):
        self.usercomponent = uc
        super().__init__(*args, **kwargs)

    def clean_key(self):
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise forms.ValidationError(_('Empty Key'))
        if "PRIVATE" in data.upper():
            raise forms.ValidationError(_('Private Key'))
        return data
