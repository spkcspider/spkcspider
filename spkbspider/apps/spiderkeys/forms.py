from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

class KeyForm(forms.ModelForm):
    from .models import PublicKey
    class Meta:
        model = PublicKey
        fields = ['key']

    def get_info(self, uc):
        if uc.name == "recovery":
            return "hash=%s;protected_for=%s;" % (self.instance.hash, getattr(settings, "RECOVERY_DELETION_PERIOD", 24*60*60))
        else:
            return "hash=%s;" % self.instance.hash


    def clean_key(self):
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise ValidationError(_('Empty Key'))
        if "PRIVATE" in data.upper():
            raise ValidationError(_('Private Key'))
        return data
