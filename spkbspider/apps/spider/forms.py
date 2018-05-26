from django import forms

from .models import AssignedProtection, Protection, UserComponent
from .protections import ProtectionType


class UserComponentForm(forms.ModelForm):
    class Meta:
        model = UserComponent
        fields = ['name']

    def __init__(self, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        assigned = None
        if self.instance and self.instance.id:
            assigned = self.instance.assigned
            if self.instance.name == "index":
                ptype = ProtectionType.authentication
            else:
                ptype = ProtectionType.access_control
            self.protections = Protection.get_forms(data=data, files=files,
                                                    prefix=prefix,
                                                    assigned=assigned,
                                                    ptype__contains=ptype)
        self.protections = []

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.instance.id:
            if self.instance.is_protected and name != self.instance.name:
                raise forms.ValidationError('Name is protected')

        if UserComponent.objects.filter(
            name=name,
            user=self.instance.user
        ).exists():
            raise forms.ValidationError('Name already exists')
        return name

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
            AssignedProtection.objects.update_or_create(
                defaults={"protectiondata": protection.cleaned_data},
                usercomponent=self.instance, protection=protection.protection
            )

    def _save_m2m(self):
        super()._save_m2m()
        self._save_protections()
