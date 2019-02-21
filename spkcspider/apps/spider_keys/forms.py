__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"


from django import forms
from django.db import models
# from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from cryptography import exceptions
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import utils, padding

from .models import PublicKey, AnchorServer, AnchorKey
# AnchorGov, ID_VERIFIERS


class KeyForm(forms.ModelForm):
    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        setattr(self.fields['key'], "hashable", True)

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
    setattr(identifier, "hashable", True)
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

    field_order = ['identifier', 'signature', 'key']

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        setattr(self.fields['key'], "hashable", True)
        if self.scope == "add":
            del self.fields["identifier"]
            del self.fields["signature"]

        if self.scope in ("add", "update"):
            self.fields["key"].queryset = self.fields["key"].queryset.filter(
                models.Q(key__contains="-----BEGIN CERTIFICATE-----")
            )
        else:
            self.fields["key"] = forms.CharField(
                initial=self.instance.key.key,
                widget=forms.TextArea
            )
            setattr(self.fields['key'], "hashable", True)

    def clean(self):
        _ = gettext
        ret = super().clean()
        try:
            pubkey = serialization.load_pem_public_key(
                ret["key"].key.encode("utf-8"), default_backend()
            )
        except exceptions.UnsupportedAlgorithm:
            self.add_error("key", forms.ValidationError(
                _("key not usable for signing"),
                code="unusable_key"
            ))
        if self.scope == "add":
            ret["signature"] = "<replaceme>"
            return ret
        chosen_hash = hashes.SHA512()
        hasher = hashes.Hash(chosen_hash, default_backend())
        raw_value = self.initial.get("identifier", None)
        hasher.update(self.fields["identifier"].to_python(
            raw_value
        ).encode("utf-8"))
        try:
            pubkey.verify(
                ret["signature"].encode("utf-8"),
                hasher.finalize(),
                padding.PSS(
                    mgf=padding.MGF1(chosen_hash),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                utils.Prehashed(chosen_hash)
            )
        except exceptions.InvalidSignature:
            self.add_error("signature", forms.ValidationError(
                _("signature incorrect"),
                code="incorrect_signature"
            ))
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
