__all__ = [
    "LinkForm", "TravelProtectionForm"
]

from django import forms
from django.contrib.auth.hashers import (
    check_password, make_password,
)
from django.utils.translation import gettext_lazy as _

from ..models import LinkContent, TravelProtection
from ..helpers import token_nonce


PROTECTION_CHOICES = [
    ("none", _("No self-protection (not recommended)")),
    ("pw", _("Password")),
    ("token", _("Token"))
]

KEEP_CHOICES = [("keep", _("Keep protection"))] + PROTECTION_CHOICES


_self_protection = _("""
    Disallows user to disable travel protection if active.
    Can be used in connection with "secret" to allow unlocking via secret
""")


class LinkForm(forms.ModelForm):

    class Meta:
        model = LinkContent
        fields = ['content']

    def __init__(self, uc, **kwargs):
        super().__init__(**kwargs)
        q = self.fields["content"].queryset
        travel = TravelProtection.objects.get_active()
        self.fields["content"].queryset = q.filter(
            strength__lte=uc.strength
        ).exclude(usercomponent__travel_protected__in=travel)


class TravelProtectionForm(forms.ModelForm):
    uc = None
    is_fake = None
    password = None
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput,
    )
    self_protection = forms.ChoiceField(
        label=_("Self protection"), help_text=_(_self_protection),
        initial="None", choices=PROTECTION_CHOICES
    )
    protection_arg = forms.CharField(initial="", required=False)

    class Meta:
        model = TravelProtection
        fields = [
            "active", "start", "stop", "login_protection", "disallow"
        ]

    def __init__(self, request, uc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uc = uc
        # elif self.travel_protection.is_active:
        #    for f in self.fields:
        #        f.disabled = True
        self.fields["protection_arg"].initial = token_nonce(30)

        if not self.instance.active and not self.instance.hashed_secret:
            del self.fields["password"]

        if self.instance.hashed_secret:
            self.fields["self_protection"].choices = KEEP_CHOICES

    def check_password(self, raw_password):
        """
        Return a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """
        def setter(raw_password):
            self.instance.hashed_secret = make_password(raw_password)
            self.instance.save(update_fields=["hashed_secret"])
        return check_password(
            raw_password, self.instance.hashed_secret, setter
        )

    def is_valid(self):
        isvalid = super().is_valid()
        if self.instance.active and self.instance.hashed_secret:
            isvalid = check_password(self.cleaned_data["password"])
        return isvalid

    def clean(self):
        ret = super().clean()
        if ret["self_protection"] == "none":
            self._password = False
        if ret["self_protection"] == "pw":
            self._password = self.cleaned_data["protection_arg"]
        elif ret["self_protection"] == "token":
            self._password = self.fields["protection_arg"].initial
        return ret

    def save(self, commit=True):
        if self._password:
            self.instance.hashed_secret = make_password(self._password)
        if self._password is False:
            self.instance.hashed_secret = None
        return super().save(commit=commit)
