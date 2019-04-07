__all__ = [
    "LinkForm", "TravelProtectionForm"
]

from django import forms
from django.conf import settings
from django.db import models
from django.contrib.auth.hashers import (
    make_password,
)
from django.utils.translation import gettext_lazy as _

from ..constants import dangerous_login_choices
from ..models import LinkContent, TravelProtection
from ..helpers import create_b64_token
from ..widgets import HTMLWidget


_extra = '' if settings.DEBUG else '.min'

PROTECTION_CHOICES = [
    ("none", _("No self-protection (not recommended)")),
    ("pw", _("Password")),
    ("token", _("Token"))
]

KEEP_CHOICES = [("keep", _("Keep protection"))] + PROTECTION_CHOICES


_self_protection = _("""Disallows user to disable travel protection if active.
 Can be used in connection with "secret" to allow unlocking via secret""")


class LinkForm(forms.ModelForm):

    class Meta:
        model = LinkContent
        fields = ['content', 'push']

    def __init__(self, uc, request, **kwargs):
        super().__init__(**kwargs)
        # if self.instance.associated:
        #     if "\x1eanchor\x1e" in self.instance.associated:
        #         self.fields["content"].disabled = True
        q = self.fields["content"].queryset
        travel = TravelProtection.objects.get_active()
        self.fields["content"].queryset = q.filter(
            strength__lte=uc.strength
        ).exclude(usercomponent__travel_protected__in=travel)
        # component auth should limit links to visible content
        # read access outside from component elsewise possible
        if request.user != uc.user and not request.is_staff:
            q = self.fields["content"].queryset
            self.fields["content"].queryset = q.filter(
                models.Q(usercomponent=uc) |
                models.Q(referenced_by__usercomponent=uc)
            )


class TravelProtectionForm(forms.ModelForm):
    uc = None
    is_fake = None
    _password = None
    password = forms.CharField(
        label=_("Old Password"),
        strip=False,
        widget=forms.PasswordInput,
    )
    self_protection = forms.ChoiceField(
        label=_("Self-protection"), help_text=_(_self_protection),
        initial="None", choices=PROTECTION_CHOICES
    )
    token_arg = forms.CharField(
        label=_("Token"),
        help_text=_("please export/copy for disabling travel mode"),
        widget=HTMLWidget
    )
    new_pw = forms.CharField(
        initial="", required=False, label=_("New Password"),
        widget=forms.PasswordInput(),
    )
    new_pw2 = forms.CharField(
        initial="", required=False, label=_("New Password (Retype)"),
        widget=forms.PasswordInput(),
    )

    class Meta:
        model = TravelProtection
        fields = [
            "active", "start", "stop", "login_protection", "disallow"
        ]

    class Media:
        js = [
            'spider_base/travelprotection.js'
        ]

    def __init__(self, request, uc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uc = uc
        self.request = request

        q = models.Q(
            user=self.uc.user,
            strength__lt=10  # don't disclose other index
        ) & ~models.Q(
            travel_protected__in=TravelProtection.objects.get_active()
        ) & ~models.Q(
            public=True  # this would easily expose the travel mode
        )

        if not getattr(settings, "DANGEROUS_TRAVEL_PROTECTIONS", False):
            self.fields["login_protection"].choices = \
                filter(
                    lambda x: x[0] not in dangerous_login_choices,
                    self.fields["login_protection"].choices
                )

        self.fields["disallow"].queryset = \
            self.fields["disallow"].queryset.filter(q)

        # elif self.travel_protection.is_active:
        #    for f in self.fields:
        #        f.disabled = True
        self.fields["token_arg"].initial = create_b64_token(30)

        if not self.instance.active or not self.instance.hashed_secret:
            del self.fields["password"]

        if self.instance.hashed_secret:
            self.fields["self_protection"].choices = KEEP_CHOICES

        # doesn't matter if it is same user, lazy
        travel = TravelProtection.objects.get_active(no_stop=True)
        self.fields["disallow"].queryset = self.fields["disallow"].queryset.\
            filter(
                ~models.Q(travel_protected__in=travel),
                user=self.uc.user, strength__lt=10
            )

    def is_valid(self):
        isvalid = super().is_valid()
        if not getattr(self, "cleaned_data", None):
            return False
        if self.instance.active and "password" in self.fields:
            isvalid = self.instance.check_password(
                self.cleaned_data["password"]
            )
        return isvalid

    def clean(self):
        ret = super().clean()
        if ret["self_protection"] == "none":
            self._password = False
        if ret["self_protection"] == "pw":
            if self.cleaned_data["new_pw"] != self.cleaned_data["new_pw2"]:
                self.add_error("new_pw", forms.ValidationError(
                    _("The two password fields didn't match.")
                ))
                self.add_error("new_pw2", forms.ValidationError(
                    _("The two password fields didn't match.")
                ))
            else:
                self._password = self.cleaned_data["new_pw"]
        elif ret["self_protection"] == "token":
            self._password = self.fields["token_arg"].initial
        return ret

    def save(self, commit=True):
        self.instance.is_fake = self.request.session.get("is_fake", False)
        if self._password:
            self.instance.hashed_secret = make_password(self._password)
        if self._password is False:
            self.instance.hashed_secret = None
        return super().save(commit=commit)
