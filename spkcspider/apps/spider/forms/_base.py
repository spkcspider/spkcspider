__all__ = ["UserComponentForm", "UserContentForm"]

from statistics import mean

from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _

from ..models import (
    AssignedProtection, Protection, UserComponent, AssignedContent
)
from ..helpers import token_nonce
from ..constants import (
    ProtectionType, NONCE_CHOICES, INITIAL_NONCE_SIZE, index_names
)

_help_text = _("""Generate new nonce with variable strength<br/>
Nonces protect against bruteforce and attackers<br/>
If you have problems with attackers (because they know the nonce),
you can invalidate it with this option and/or add protections<br/>
<span style="color:red;">
Warning: this removes also access for all services you gave the link<br/>
Warning: if you rely on nonces make sure user component has <em>public</em>
not set
</span>
""")


class UserComponentForm(forms.ModelForm):
    protections = None
    new_nonce = forms.ChoiceField(
        label=_("New Nonce"), help_text=_help_text,
        required=False, initial="", choices=NONCE_CHOICES
    )

    class Meta:
        model = UserComponent
        fields = [
            'name', 'featured', 'public', 'description', 'required_passes',
            'token_duration',
        ]
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _('UserComponent name already exists')
            }
        }

    def __init__(self, request, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        self.fields["new_nonce"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_nonce"].choices
        )
        if not (
            request.user.is_superuser or
            request.user.has_perm('spider_base.can_feature')
        ) or request.session.get("is_fake", False):
            self.fields['featured'].disabled = True

        if self.instance and self.instance.id:
            assigned = self.instance.protections
            if self.instance.name_protected:
                self.fields["name"].disabled = True
            if self.instance.no_public:
                self.fields["public"].disabled = True
                self.fields.pop("featured", None)
            if self.instance.name in index_names:
                self.fields.pop("featured", None)
                self.fields["required_passes"].help_text = _(
                    "How many protections must be passed to login?"
                    "Minimum is 1, no matter what selected"
                )
                ptype = ProtectionType.authentication.value
            else:

                ptype = ProtectionType.access_control.value
            self.protections = Protection.get_forms(data=data, files=files,
                                                    prefix=prefix,
                                                    assigned=assigned,
                                                    ptype=ptype)
            self.protections = list(self.protections)
        else:
            self.fields["new_nonce"].initial = INITIAL_NONCE_SIZE
            self.fields["new_nonce"].choices = \
                self.fields["new_nonce"].choices[1:]
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
            if self.cleaned_data['name'] in index_names:
                raise forms.ValidationError(
                    _('Forbidden Name'),
                    code="forbidden_name"
                )
        for protection in self.protections:
            protection.full_clean()
        self.cleaned_data["strength"] = 0
        if self.cleaned_data["name"] in index_names:
            self.cleaned_data["strength"] = 10
            return ret
        if not self.cleaned_data["public"]:
            self.cleaned_data["strength"] += 5

        if self.instance and getattr(self.instance, "id", None):
            fail_strength = 0
            amount_regular = 0
            strengths = []
            for protection in self.protections:
                if not protection.cleaned_data.get("active", False):
                    continue

                if len(str(protection.cleaned_data)) > 1_000_000:
                    raise forms.ValidationError(
                        _("Protection >1 mb: %(name)s"),
                        params={"name": protection}
                    )
                if protection.cleaned_data.get("instant_fail", False):
                    fail_strength = max(
                        fail_strength, protection.get_strength()
                    )
                else:
                    strengths.append(protection.get_strength())
                    amount_regular += 1
            strengths.sort()
            if self.cleaned_data["required_passes"] > 0:
                if amount_regular == 0:
                    strengths = 4  # can only access component via own login
                else:
                    strengths = round(mean(strengths[:ret["required_passes"]]))
            else:
                strengths = 0
            self.cleaned_data["strength"] += max(strengths, fail_strength)
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

    def save(self, commit=True):
        if self.cleaned_data["new_nonce"] != "":
            print(
                "Old nonce for Component id:", self.instance.id,
                "is", self.instance.nonce
            )
            self.instance.nonce = token_nonce(
                int(self.cleaned_data["new_nonce"])
            )

        self.instance.strength = self.cleaned_data["strength"]
        return super().save(commit=commit)


class UserContentForm(forms.ModelForm):
    prefix = "content_control"
    new_nonce = forms.ChoiceField(
        label=_("New Nonce"), help_text=_(_help_text),
        required=False, initial="", choices=NONCE_CHOICES
    )

    class Meta:
        model = AssignedContent
        fields = ['usercomponent']
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _(
                    'AssignedContent type/configuration can '
                    'only exist once by usercomponent'
                )
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.usercomponent.user
        query = UserComponent.objects.filter(user=user)
        self.fields["usercomponent"].queryset = query

        self.fields["new_nonce"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_nonce"].choices
        )

        if not self.instance.id:
            self.fields["new_nonce"].initial = INITIAL_NONCE_SIZE
            self.fields["new_nonce"].choices = \
                self.fields["new_nonce"].choices[1:]

    def save(self, commit=True):
        if self.cleaned_data["new_nonce"] != "":
            print(
                "Old nonce for Content id:", self.instance.id,
                "is", self.instance.nonce
            )
            self.instance.nonce = token_nonce(
                int(self.cleaned_data["new_nonce"])
            )
        return super().save(commit=commit)
