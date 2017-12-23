from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

class KeyForm(forms.ModelForm):
    from .models import PublicKey

    usercomponent = None
    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def __init__(self, *args, **kwargs):
        self.usercomponent = kwargs.pop("usercomponent")
        super().__init__(*args, **kwargs)

    def is_valid(self):
        return False if not super().is_valid()
        # shortcut if key matches
        if hasattr(self, "instance") and self.instance:
            return True if self.object.key == self.cleaned_data["key"]
        h = hashlib.new(settings.KEY_HASH_ALGO)
        h.update(self.cleaned_data["key"].encode("utf-8", "ignore"))
        _hash = h.hexdigest()
        # check that the user does not inpersonate an other
        return not PublicKey.objects.filter(hash=_hash).exclude(associated__usercomponent__user=self.usercomponent.user).exists()

    def get_info(self):
        if self.usercomponent.name == "recovery":
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
