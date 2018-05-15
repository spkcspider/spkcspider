from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import AssignedProtection, Protection, UserComponent
from .protections import installed_protections

class UserComponentForm(forms.ModelForm):
    class Meta:
        model = UserComponent
        fields = ['name']
        #widgets = {"user": forms.HiddenInput()}

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, *args, **kwargs):
        super().__init__(*args, data=data, files=files, auto_id=auto_id, prefix=prefix, **kwargs)
        assigned = None
        if self.instance and self.instance.id:
            assigned = self.instance.assigned
            if self.instance.name == "index":
                ptypes = [0]
            else:
                ptypes = [1,2]
        else:
            ptypes = [0]
        self.protections = Protection.get_forms(data=data, files=files, prefix=prefix, assigned=assigned, ptypes=ptypes)

    def is_valid(self):
        isvalid = super().is_valid()
        for protection in self.protections:
            if not protection.is_valid():
                isvalid = False
        return isvalid

    def _save_protections(self):
        for protection in self.protections:
            if not protection.active:
                continue
            AssignedProtection.objects.update_or_create(defaults={"protectiondata": protection.cleaned_data}, usercomponent=self.instance, protection=protection.protection)

    def _save_m2m(self):
        super()._save_m2m()
        self._save_protections()


    # don't disallow creation of internal names
    #def clean_name(self):
    #    data = self.cleaned_data['name']
    #    if data == "":
    #        raise forms.ValidationError(_('Empty name'))
    #    # don't disallow recreation of UserComponents with special names
    #    #if data.lower() in ["index", "recovery"]:
    #    #    raise forms.ValidationError(_('Internal names'))
    #    return data
