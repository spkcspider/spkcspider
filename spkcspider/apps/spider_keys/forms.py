__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"

import binascii

from django.db import models
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from cryptography import exceptions
from cryptography.hazmat.primitives.asymmetric import padding

from spkcspider.apps.spider.fields import MultipleOpenChoiceField
from spkcspider.apps.spider.widgets import ListWidget
from spkcspider.apps.spider.models import TravelProtection, AssignedContent
from spkcspider.constants import loggedin_active_tprotections


from .models import PublicKey, AnchorServer, AnchorKey


_help_text_key = _(
    '"Public Key"-Content for signing identifier. It is recommended to use different keys for signing and encryption. '  # noqa: E501
    "Reason herefor is, that with a change of the signing key the whole anchor gets invalid and the signing key should be really carefully saved away. "  # noqa: E501
    "In contrast the encryption keys can be easily exchanged and should be available for encryption"  # noqa: E501
)


class KeyForm(forms.ModelForm):
    hash_algorithm = forms.CharField(
        widget=forms.HiddenInput(), disabled=True
    )
    setattr(hash_algorithm, "hashable", False)

    class Meta:
        model = PublicKey
        fields = ['key']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.initial["hash_algorithm"] = settings.SPIDER_HASH_ALGORITHM.name
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
    key = forms.ModelChoiceField(
        queryset=AssignedContent.objects.filter(
            ctype__name="PublicKey",
            info__contains="\x1epubkeyhash="
        )
    )

    scope = ""

    class Meta:
        model = AnchorKey
        fields = ['key', 'signature']

    field_order = ['identifier', 'signature', 'key']

    def __init__(self, scope, request, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.instance.id:
            self.initial["key"] = \
                self.instance.associated.attached_to_content
        if self.scope == "add":
            del self.fields["identifier"]
            del self.fields["signature"]
            del self.fields["anchor_type"]
            # self.fields["signature"].disabled = True
            # self.fields["signature"].required = False

        if self.scope in ("add", "update"):
            travel = TravelProtection.objects.get_active_for_request(request)
            travel = travel.filter(
                login_protection__in=loggedin_active_tprotections
            )
            self.fields["key"].queryset = \
                self.fields["key"].queryset.exclude(
                    models.Q(usercomponent__travel_protected__in=travel) |
                    models.Q(travel_protected__in=travel)
                ).filter(
                    usercomponent=self.instance.associated.usercomponent
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
        pubkey = self.cleaned_data.get("key")
        if pubkey:
            pubkey = pubkey.content.get_key_ob()
            if not pubkey:
                self.add_error("key", forms.ValidationError(
                    _("key not usable for signing"),
                    code="unusable_key"
                ))
        if self.scope == "add":
            ret["signature"] = "<replaceme>"
            return ret
        if not pubkey:
            return
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

    def save(self, commit=True):
        self.instance.associated.attached_to_content = \
            self.cleaned_data["key"]
        return super().save(commit)


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
