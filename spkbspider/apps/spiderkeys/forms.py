from django import forms
from django.utils.translation import ugettext_lazy as _

class ProtectionForm(forms.ModelForm):
    from .models import PublicKey
    class Meta:
        model = PublicKey
        fields = ['key']

    def clean_key(self):
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise ValidationError(_('Empty Key'))
        if "PRIVATE" in data.upper():
            raise ValidationError(_('Private Key'))
        return data
