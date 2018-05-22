from django import forms

from .models import AssignedProtection, Protection, UserComponent


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
                ptypes = [0]
            else:
                ptypes = [1, 2]
        else:
            ptypes = [0]
        self.protections = Protection.get_forms(data=data, files=files,
                                                prefix=prefix,
                                                assigned=assigned,
                                                ptypes=ptypes)

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
