__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"

import binascii

from django import forms
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from cryptography import exceptions
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from spkcspider.apps.spider.fields import MultipleOpenChoiceField
from spkcspider.apps.spider.widgets import ListWidget

from .models import PublicKey, AnchorServer, AnchorKey


class KeyForm(forms.ModelForm):
    class Meta:
        model = PublicKey
        fields = ['key']

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
    anchor_type = forms.CharField(disabled=True, initial="url")
    setattr(identifier, "hashable", True)
    scope = ""
    old_urls = MultipleOpenChoiceField(
        widget=ListWidget(
            format_type="url", item_label=_("Url to superseded anchor")
        ), required=False
    )

    class Meta:
        model = AnchorServer
        fields = ["new_url", "old_urls"]

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["identifier"]
            del self.fields["anchor_type"]
            del self.fields["new_url"]

    def clean_old_urls(self):
        values = self.cleaned_data["old_urls"]
        if not isinstance(values, list):
            raise forms.ValidationError(
                _("Invalid format"),
                code='invalid_format'
            )
        return values

    def clean(self):
        _ = gettext
        ret = super().clean()
        if ret.get("new_url", None) and ret.get("old_urls", []):
            raise forms.ValidationError(
                _(
                    "Specify either replacement url or "
                    "urls to superseding anchors"
                ),
                code='invalid_choices'
            )
        return ret


class AnchorKeyForm(forms.ModelForm):
    identifier = forms.CharField(disabled=True)
    anchor_type = forms.CharField(disabled=True, initial="signature")
    scope = ""

    class Meta:
        model = AnchorKey
        fields = ['key', 'signature']

    field_order = ['identifier', 'signature', 'key']

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["identifier"]
            del self.fields["signature"]
            del self.fields["anchor_type"]
            # self.fields["signature"].disabled = True
            # self.fields["signature"].required = False

        if self.scope in ("add", "update"):
            self.fields["key"].queryset = self.fields["key"].queryset.filter(
                models.Q(key__contains="-----BEGIN CERTIFICATE-----") |
                models.Q(key__contains="-----BEGIN PUBLIC KEY-----")
            )
        elif self.scope in ("raw", "list", "view"):
            self.fields["key"] = forms.CharField(
                initial=self.instance.key.key,
                widget=forms.TextArea
            )
            setattr(self.fields['key'], "hashable", True)

    def clean(self):
        _ = gettext
        ret = super().clean()
        try:
            if "-----BEGIN CERTIFICATE-----" in self.cleaned_data["key"].key:
                pubkey = load_pem_x509_certificate(
                    ret["key"].key.encode("utf-8"), default_backend()
                ).public_key()
            else:
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
        chosen_hash = settings.SPIDER_HASH_ALGORITHM
        try:
            pubkey.verify(
                binascii.unhexlify(ret["signature"]),
                ret["identifier"].encode("utf-8"),
                padding.PSS(
                    mgf=padding.MGF1(chosen_hash),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                chosen_hash
            )
        except exceptions.InvalidSignature:
            self.add_error("signature", forms.ValidationError(
                _("signature incorrect"),
                code="incorrect_signature"
            ))
        except (binascii.Error, KeyError, ValueError):
            self.add_error("signature", forms.ValidationError(
                _("signature malformed or missing"),
                code="malformed_signature"
            ))
        return ret


# class AnchorGovForm(forms.ModelForm):
#    identifier = forms.CharField(disabled=True, widget=forms.HiddenInput())
#    anchor_type = forms.CharField(disabled=True, initial="gov")
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
