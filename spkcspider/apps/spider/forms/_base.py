__all__ = ["UserComponentForm", "UserContentForm"]

import logging
from statistics import mean

from django import forms
from django.db import models
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _

from ..models import (
    AssignedProtection, Protection, UserComponent, AssignedContent,
    ContentVariant, AuthToken
)
from ..helpers import create_b64_id_token
from ..constants import (
    ProtectionType, VariantType, STATIC_TOKEN_CHOICES,
    INITIAL_STATIC_TOKEN_SIZE,
    index_names, protected_names
)
from ..signals import move_persistent

_help_text_static_token = _("""Generate a new static token with variable strength<br/>
Tokens protect against bruteforce and attackers<br/>
If you have problems with attackers (because they know the token),
you can invalidate it with this option and/or add protections<br/>
<table style="color:red;">
<tr>
<td>Warning:</td><td>this removes also access for all services you gave the link<td/>
</tr>
<tr>
<td style="vertical-align: top">Warning:</td><td>public user components disclose static token, regenerate after removing
public attribute from component for restoring protection</td>
</tr>
</table>
""")  # noqa: E501


_help_text_features = _("""
Note: persistent Features (=features which use a persistent token) require and enable "Persistence"
""")  # noqa: E501


class UserComponentForm(forms.ModelForm):
    protections = None
    new_static_token = forms.ChoiceField(
        label=_("New static token"), help_text=_help_text_static_token,
        required=False, initial="", choices=STATIC_TOKEN_CHOICES
    )

    class Meta:
        model = UserComponent
        fields = [
            'name', 'description', 'public', 'featured',
            'features', 'primary_anchor', 'required_passes', 'token_duration'
        ]
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _('Name of User Component already exists')
            }
        }
        help_texts = {
            'features': _help_text_features,
        }
        widgets = {
            'features': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, request, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        self.fields["new_static_token"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_static_token"].choices
        )
        if not (
            request.user.is_superuser or
            request.user.has_perm('spider_base.can_feature')
        ) or request.session.get("is_fake", False):
            self.fields['featured'].disabled = True

        self.fields["features"].queryset = (
            self.fields["features"].queryset &
            request.user.spider_info.allowed_content.all()
        ).order_by("name")

        if self.instance and self.instance.id:
            assigned = self.instance.protections
            if self.instance.name in protected_names:
                self.fields["name"].disabled = True
            if not self.instance.is_public_allowed:
                self.fields["public"].disabled = True
                self.fields.pop("featured", None)
            self.fields["primary_anchor"].queryset = \
                self.fields["primary_anchor"].queryset.filter(
                    usercomponent=self.instance
                )
            if self.instance.name in index_names:
                self.fields.pop("features", None)
                self.fields.pop("featured", None)
                self.fields["required_passes"].help_text = _(
                    "How many protections must be passed to login?<br/>"
                    "Minimum is 1, no matter what selected"
                )
                ptype = ProtectionType.authentication.value
            else:

                ptype = ProtectionType.access_control.value
            self.protections = Protection.get_forms(data=data, files=files,
                                                    prefix=prefix,
                                                    assigned=assigned,
                                                    ptype=ptype,
                                                    request=request)
            self.protections = list(self.protections)
        else:
            self.fields.pop("primary_anchor", None)
            self.fields["new_static_token"].initial = INITIAL_STATIC_TOKEN_SIZE
            self.fields["new_static_token"].choices = \
                self.fields["new_static_token"].choices[1:]
            self.protections = []
            self.fields["required_passes"].initial = 1

    @property
    def media(self):
        """Return all media required to render the widgets on this form."""
        media = super().media
        for protection in self.protections:
            media = media + protection.media
        return media

    def is_valid(self):
        isvalid = super().is_valid()
        for protection in self.protections:
            if not protection.is_valid():
                isvalid = False
        return isvalid

    def clean(self):
        ret = super().clean()
        if 'name' not in self.cleaned_data:
            # ValidationError so return, calculations won't work here
            return
        if not self.instance or not getattr(self.instance, "id", None):
            # TODO: cleanup into protected_names/forbidden_names
            if self.cleaned_data['name'] in protected_names:
                raise forms.ValidationError(
                    _('Forbidden Name'),
                    code="forbidden_name"
                )
        for protection in self.protections:
            protection.full_clean()
        self.cleaned_data["strength"] = 0
        max_prot_strength = 0
        if self.cleaned_data["name"] in index_names:
            self.cleaned_data["strength"] = 10
            return ret
        if not self.cleaned_data["public"]:
            self.cleaned_data["strength"] += 5

        if self.instance and getattr(self.instance, "id", None):
            # instant fail strength
            fail_strength = 0
            # regular protections strength
            amount_regular = 0
            strengths = []
            for protection in self.protections:
                if not protection.cleaned_data.get("active", False):
                    continue

                if len(str(protection.cleaned_data)) > 1000000:
                    raise forms.ValidationError(
                        _("Protection >1 mb: %(name)s"),
                        params={"name": protection}
                    )
                if protection.cleaned_data.get("instant_fail", False):
                    s = protection.get_strength()
                    if s[1] > max_prot_strength:
                        max_prot_strength = s[1]
                    fail_strength = max(
                        fail_strength, s[0]
                    )
                else:
                    s = protection.get_strength()
                    if s[1] > max_prot_strength:
                        max_prot_strength = s[1]
                    strengths.append(s[0])
                    amount_regular += 1
            strengths.sort()
            if self.cleaned_data["required_passes"] > 0:
                if amount_regular == 0:
                    # login or token only
                    # not 10 because 10 is also used for uniqueness
                    strengths = 4
                else:
                    strengths = round(mean(strengths[:ret["required_passes"]]))
            else:
                strengths = 0
            self.cleaned_data["strength"] += max(strengths, fail_strength)
        self.cleaned_data["can_auth"] = max_prot_strength >= 4
        if any(map(
            lambda x: VariantType.persist.value in x.ctype,
            self.cleaned_data["features"]
        )):
            self.cleaned_data["features"] |= ContentVariant.objects.filter(
                name="Persistence"
            )
        min_strength = self.cleaned_data["features"].filter(
            strength__gt=self.cleaned_data["strength"]
        ).aggregate(m=models.Max("strength"))["m"]
        # min_strength is None if no features are higher than allowed
        if min_strength:
            self.add_error("features", forms.ValidationError(
                _(
                    "selected features require "
                    "higher protection strength: %s"
                ) % min_strength,
                code="unsufficient_strength"
            ))
        return self.cleaned_data

    def _save_protections(self):
        for protection in self.protections:
            cleaned_data = protection.cleaned_data
            t = AssignedProtection.objects.filter(
                usercomponent=self.instance, protection=protection.protection
            ).first()
            if not cleaned_data["active"] and not t:
                continue
            if not t:
                t = AssignedProtection(
                    usercomponent=self.instance,
                    protection=protection.protection
                )
            t.active = cleaned_data.pop("active")
            t.instant_fail = cleaned_data.pop("instant_fail")
            t.data = cleaned_data
            t.save()

    def _save_m2m(self):
        super()._save_m2m()
        self._save_protections()
        if self.cleaned_data["new_static_token"] != "":
            if self.instance.token:
                print(
                    "Old nonce for Component id:", self.instance.id,
                    "is", self.instance.token
                )
            self.instance.token = create_b64_id_token(
                self.instance.id, "/",
                int(self.cleaned_data["new_static_token"])
            )
            self.instance.save(update_fields=["token"])

    def save(self, commit=True):
        self.instance.strength = self.cleaned_data["strength"]
        self.instance.can_auth = self.cleaned_data["can_auth"]
        return super().save(commit=commit)


class UserContentForm(forms.ModelForm):
    prefix = "content_control"
    new_static_token = forms.ChoiceField(
        label=_("New static token"), help_text=_help_text_static_token,
        required=False, initial="", choices=STATIC_TOKEN_CHOICES
    )
    migrate_primary_anchor = forms.BooleanField(
        label=_("Migrate primary anchor"),
        help_text=_(
            "Set as primary anchor on target component. "
            "Move tokens and all persistent dependencies. "
            "Elsewise anchor persistent tokens on the component and leave the "
            "dependencies untouched."
        ),
        required=False, initial=False
    )

    class Meta:
        model = AssignedContent
        fields = ['usercomponent']
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _(
                    "Unique Content already exists"
                )
            }
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["new_static_token"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_static_token"].choices
        )
        user = self.instance.usercomponent.user

        if request.session.get("is_fake", False):
            q = ~models.Q(name="index")
        else:
            q = ~models.Q(name="fake_index")
        query = UserComponent.objects.filter(q, user=user)
        self.fields["usercomponent"].queryset = query

        show_primary_anchor_mig = False
        if self.instance.id:
            if (
                request.user == user and
                self.instance.primary_anchor_for.exists()
            ):
                # can only migrate if a) created, b) real user
                show_primary_anchor_mig = True
        else:
            self.fields["new_static_token"].initial = INITIAL_STATIC_TOKEN_SIZE
            self.fields["new_static_token"].choices = \
                self.fields["new_static_token"].choices[1:]
        if request.user != user and not request.is_staff:
            del self.fields["usercomponent"]

        if not show_primary_anchor_mig:
            del self.fields["migrate_primary_anchor"]

    def update_anchor(self):
        if not self.instance.primary_anchor_for.exists():
            return
        if self.instance.primary_anchor_for == self.instance.usercomponent:
            return
        if self.cleaned_data.get("migrate_primary_anchor", False):
            # no signals
            self.instance.primary_anchor_for.set(
                self.instance.usercomponent, bulk=True
            )
            tokens = AuthToken.objects.filter(
                persist=self.instance.id
            )
            tokens.update(
                usercomponent=self.instance.usercomponent,
            )
            # this is how to move persistent content
            results = move_persistent.send_robust(
                AuthToken, tokens=tokens,
                to=self.instance.usercomponent
            )
            for (receiver, result) in results:
                if isinstance(result, Exception):
                    logging.error(
                        "%s failed", receiver, exc_info=result
                    )
        else:
            self.instance.primary_anchor_for.clear(bulk=False)
            # token migrate to component via signal

    def _save_m2m(self):
        super()._save_m2m()
        self.update_anchor()
        if self.cleaned_data.get("new_static_token", ""):
            if self.instance.token:
                print(
                    "Old nonce for Content id:", self.instance.id,
                    "is", self.instance.token
                )
            self.instance.token = create_b64_id_token(
                self.instance.id, "/",
                int(self.cleaned_data["new_static_token"])
            )
            self.instance.save(update_fields=["token"])

    def save(self, commit=True):
        ret = super().save(commit=commit)
        if commit:
            self.update_anchor()
        return ret
