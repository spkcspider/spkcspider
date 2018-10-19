__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"


from django import forms
# from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from .models import PublicKey, AnchorServer, AnchorKey
# AnchorGov, ID_VERIFIERS

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend_
default_backend = default_backend_()


class KeyForm(forms.ModelForm):
    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def clean_key(self):
        _ = gettext
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise forms.ValidationError(
                _('Empty Key'),
                code="empty"
            )
        if "PRIVATE" in data.upper():
            raise forms.ValidationError(
                _('Private Key')
            )
        return data


class AnchorServerForm(forms.ModelForm):
    identifier = forms.CharField(disabled=True)
    scope = ""

    class Meta:
        model = AnchorServer
        fields = []

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["identifier"]


class AnchorKeyForm(forms.ModelForm):
    identifier = forms.CharField(disabled=True)
    scope = ""

    class Meta:
        model = AnchorKey
        fields = ['key', 'signature']

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["identifier"]

    def clean(self):
        ret = super().clean()
        if "-----BEGIN CERTIFICATE-----" in ret["key"].key:
            pubkey = serialization.load_pem_public_key(
                ret["key"].key, default_backend
            )
        else:
            pubkey = serialization.load_ssh_public_key(
                ret["key"].key, default_backend
            )
        #pubkey.verify()
        # validate signature
        return self.cleaned_data


# class AnchorGovForm(forms.ModelForm):
#    identifier = forms.CharField(disabled=True, widget=forms.HiddenInput())
#    scope = ""
#
#    class Meta:
#        model = AnchorGov
#        fields = ['idtype', 'token']
#
#    def __init__(self, scope, **kwargs):
#        self.scope = scope
#        super().__init__(**kwargs)
#
#    def clean(self):
#        self.cleaned_data["type"] = "gov"
#        self.cleaned_data["identifier"] = self.instance.get_identifier()
#        self.cleaned_data["format"] = "gov_{verifier}_{token}"
#        if self.scope not in ["add", "update"]:
#            self.cleaned_data["verifier"] = ID_VERIFIERS[self.idtype]
#        del self.cleaned_data["idtype"]
#        return self.cleaned_data
