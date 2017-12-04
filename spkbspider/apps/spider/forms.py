from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import AssignedProtection, UserComponent

class UserComponentCreateForm(forms.ModelForm):
    class Meta:
        model = UserComponent
        fields = ['name', 'protections']

    # don't disallow creation of internal names
    #def clean_name(self):
    #    data = self.cleaned_data['name']
    #    if data == "":
    #        raise forms.ValidationError(_('Empty name'))
    #    # don't disallow recreation of UserComponents with special names
    #    #if data.lower() in ["index", "recovery"]:
    #    #    raise forms.ValidationError(_('Internal names'))
    #    return data

class UserComponentUpdateForm(forms.ModelForm):
    protection_forms = None
    #contents = forms.ModelMultipleChoiceField()

    class Meta:
        model = UserComponent
        fields = ['protections']

    def __init__(self, protection_forms, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protection_forms = protection_forms

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
            f.save()
        return ret
