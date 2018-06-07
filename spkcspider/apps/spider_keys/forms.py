import hashlib

from django import forms
from django.conf import settings
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

    def is_valid(self):
        if not super().is_valid():
            return False
        # shortcut if key matches
        if hasattr(self, "instance") and self.instance:
            if self.instance.key == self.cleaned_data["key"]:
                return True
        h = hashlib.new(settings.KEY_HASH_ALGO)
        h.update(self.cleaned_data["key"].encode("utf-8", "ignore"))
        _hash = h.hexdigest()
        # check that the user does not inpersonate an other
        return not PublicKey.objects.filter(
            hash=_hash
        ).exclude(
            associated__usercomponent__user=self.usercomponent.user
        ).exists()

    def clean_key(self):
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise forms.ValidationError(_('Empty Key'))
        if "PRIVATE" in data.upper():
            raise forms.ValidationError(_('Private Key'))
        return data
