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


PROTECTION_CHOICES = {
    "none": _("No self-protection (not recommended)"),
    "pw": _("Password"),
    "token": _("Token")
}


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

    def __init__(self, uc, is_fake, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uc = uc
        self.is_fake = is_fake
        # elif self.travel_protection.is_active:
        #    for f in self.fields:
        #        f.disabled = True
        self.fields["protection_arg"].initial = token_nonce(30)

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
        if self.is_fake and self.instance.hashed_secret:
            isvalid = check_password(self.cleaned_data["protection_arg"])
        return isvalid

    def save(self, commit=True):
        if self.cleaned_data["self_protection"] != "none":
            if self.cleaned_data["self_protection"] == "pw":
                raw_password = self.cleaned_data["protection_arg"]
            elif self.cleaned_data["self_protection"] == "token":
                raw_password = self.fields["protection_arg"].initial

            self.instance.hashed_secret = make_password(raw_password)
        return super().save(commit=commit)
