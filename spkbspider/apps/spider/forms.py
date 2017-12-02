from django import forms
from django.utils.translation import ugettext_lazy as _

import swapper

from .models import AssignedProtection, UserComponent


class UserComponentForm(forms.ModelForm):
    protection_forms = None
    class Meta:
        model = UserComponent
        fields = ['contents', 'protections']

    def __init__(self, protection_forms, *args, **kwargs):
        super().__init__(*args, **kwargs)
        protection_forms = protection_forms

    def is_valid(self):
        isvalid = self.is_bound and not self.errors
        for f in self.protection_forms:
            t = f.is_valid()
            if isvalid:
                isvalid = t
        return isvalid

    def clean(self):
        ret = super().clean()
        for f in self.protection_forms:
            f.clean()
        return ret

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)
        for f in self.protection_forms:
            f.save(*args, **kwargs)
        return ret
