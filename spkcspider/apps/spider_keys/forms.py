__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm", "AnchorGovForm"]


from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import PublicKey, AnchorServer, AnchorKey, AnchorGov, ID_VERIFIERS


class KeyForm(forms.ModelForm):

    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def clean_key(self):
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise forms.ValidationError(_('Empty Key'))
        if "PRIVATE" in data.upper():
            raise forms.ValidationError(_('Private Key'))
        return data


class AnchorServerForm(forms.ModelForm):

    class Meta:
        model = AnchorServer
        fields = []

    def clean(self):
        self.cleaned_data["type"] = "server"
        self.cleaned_data["format"] = "server_{identifier}"
        self.cleaned_data["identifier"] = self.instance.get_identifier()
        return self.cleaned_data


class AnchorKeyForm(forms.ModelForm):

    class Meta:
        model = AnchorKey
        fields = ['key', 'signature']

    def clean(self):
        self.cleaned_data["type"] = "key"
        self.cleaned_data["format"] = "key_{hash}"
        self.cleaned_data["identifier"] = self.instance.get_identifier()
        return self.cleaned_data


class AnchorGovForm(forms.ModelForm):
    scope = ""

    class Meta:
        model = AnchorGov
        fields = ['idtype', 'token']

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)

    def clean(self):
        self.cleaned_data["type"] = "gov"
        self.cleaned_data["identifier"] = self.instance.get_identifier()
        self.cleaned_data["format"] = "gov_{verifier}_{token}"
        if self.scope not in ["add", "update"]:
            self.cleaned_data["verifier"] = ID_VERIFIERS[self.idtype]
        del self.cleaned_data["idtype"]
        return self.cleaned_data
