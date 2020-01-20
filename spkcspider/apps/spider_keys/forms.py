__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"

import binascii

from cryptography import exceptions
from cryptography.hazmat.primitives.asymmetric import padding
from django import forms
from django.conf import settings
from django.db import models
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from spkcspider.apps.spider.fields import MultipleOpenChoiceField
from spkcspider.apps.spider.forms.base import DataContentForm
from spkcspider.apps.spider.models import AssignedContent, AttachedBlob
from spkcspider.apps.spider.queryfilters import loggedin_active_tprotections_q
from spkcspider.apps.spider.widgets import ListWidget, UploadTextareaWidget

_help_text_key = _(
    '"Public Key"-Content for signing identifier. It is recommended to use different keys for signing and encryption. '  # noqa: E501
    "Reason herefor is, that with a change of the signing key the whole anchor gets invalid and the signing key should be really carefully saved away. "  # noqa: E501
    "In contrast the encryption keys can be easily exchanged and should be available for encryption"  # noqa: E501
)

_help_text_sig = _("""Signature of Identifier (hexadecimal-encoded)""")


def valid_pkey_properties(key):
    _ = gettext
    if "PRIVAT" in key.upper():
        raise forms.ValidationError(_('Private Key'))
    if key.strip() != key:
        raise forms.ValidationError(_('Not trimmed'))
    if len(key) < 100:
        raise forms.ValidationError(_('Not a key'))


class KeyForm(DataContentForm):
    hash_algorithm = forms.CharField(
        widget=forms.HiddenInput(), disabled=True
    )
    key = forms.CharField(
        widget=UploadTextareaWidget(), strip=True, required=False,
        validators=[valid_pkey_properties]
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        key = None
        if self.instance.pk:
            key = self.instance.associated.attachedblobs.filter(
                name="key"
            ).first()
        key = key.as_bytes.decode("ascii") if key else ""
        self.initial["key"] = key
        self.initial["hash_algorithm"] = settings.SPIDER_HASH_ALGORITHM.name
        setattr(self.fields['hash_algorithm'], "hashable", False)
        setattr(self.fields['key'], "hashable", True)

    def get_prepared_attachements(self):
        b = None
        if self.instance.pk:
            b = self.instance.associated.attachedblobs.filter(
                name="key"
            ).first()
        if not b:
            b = AttachedBlob(
                unique=True, name="key", content=self.instance.associated
            )
        if isinstance(self.cleaned_data["key"], str):
            b.blob = self.cleaned_data["key"].encode("ascii")
        else:
            b.blob = self.cleaned_data["key"]

        return {
            "attachedblobs": [b]
        }


class AnchorServerForm(DataContentForm):
    identifier = forms.CharField(disabled=True)
    anchor_type = forms.CharField(disabled=True, initial="url")
    setattr(identifier, "hashable", True)
    scope = ""
    new_url = forms.URLField(
        required=False,
        help_text=_(
            "Url to new anchor (in case this one is superseded)"
        )
    )
    old_urls = MultipleOpenChoiceField(
        widget=ListWidget(
            items={
                "format_type": "url"
            }, item_label=_("Url to superseded anchor")
        ), required=False,
        help_text=_(
            "Superseded anchor urls"
        )
    )
    quota_fields = {"new_url": None, "old_urls": list}

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


class AnchorKeyForm(DataContentForm):
    identifier = forms.CharField(disabled=True)
    signature = forms.CharField(
        help_text=_help_text_sig
    )
    key = forms.ModelChoiceField(
        queryset=AssignedContent.objects.filter(
            ctype__name="PublicKey",
            info__contains="\x1epubkeyhash="
        )
    )
    anchor_type = forms.CharField(disabled=True, initial="signature")

    scope = ""
    quota_fields = {"signature": None}

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
            travel = \
                AssignedContent.travel.get_active_for_request(
                    request
                )
            travel = travel.filter(
                loggedin_active_tprotections_q
            )
            self.fields["key"].queryset = \
                self.fields["key"].queryset.exclude(
                    models.Q(usercomponent__travel_protected__in=travel) |
                    models.Q(travel_protected__in=travel)
                ).filter(
                    usercomponent=self.instance.associated.usercomponent
                )
        elif self.scope in ("raw", "list", "view"):
            blob = self.initial["key"].attachedblobs.get(
                name="key"
            )
            self.initial["key"] = blob.as_bytes.decode("ascii")
            self.fields["key"] = forms.CharField(
                widget=forms.Textarea()
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
                ret["identifier"].encode("ascii"),
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
