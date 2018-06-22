
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import (
    AssignedProtection, Protection, UserComponent, UserContent, token_nonce
)
from .protections import ProtectionType
from .auth import SpiderAuthBackend

_help_text = """Generate new nonce with variable strength<br/>
Nonces protect against bruteforce and attackers<br/>
If you have problems with attackers (because they know the nonce),
you can invalidate it with this option<br/>
<span style="color:red;">
Warning: this removes also access for all services you gave the
<em>%s</em> link</span>"""

NONCE_CHOICES = [
    ("", ""),
    ("3", _("low (3 Bytes)")),
    ("12", _("medium (12 Bytes)")),
    ("30", _("high (30 Bytes)")),
]

INITIAL_NONCE_SIZE = "12"


class UserComponentForm(forms.ModelForm):
    protections = None
    new_nonce = forms.ChoiceField(
        label=_("New Nonce"), help_text=_(_help_text % 'User Component'),
        required=False, initial="", choices=NONCE_CHOICES
    )

    class Meta:
        model = UserComponent
        fields = ['name']

    def __init__(self, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        if self.instance and self.instance.id:
            assigned = self.instance.protected_by
            if self.instance.is_protected:
                self.fields["name"].disabled = True
            if self.instance.name == "index":
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
            self.fields["new_nonce"].choices = NONCE_CHOICES[1:]
            self.protections = []

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.instance.id:
            if self.instance.is_protected and name != self.instance.name:
                raise forms.ValidationError('Name is protected')

        if name != self.instance.name and UserComponent.objects.filter(
            name=name,
            user=self.instance.user
        ).exists():
            raise forms.ValidationError('Name already exists')
        return name

    def is_valid(self):
        isvalid = super().is_valid()
        for protection in self.protections:
            if not protection.is_valid():
                isvalid = False
        return isvalid

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
        return super().save(commit=commit)


class UserContentForm(forms.ModelForm):
    prefix = "content_control"
    new_nonce = forms.ChoiceField(
        label=_("New Nonce"), help_text=_(_help_text % 'User Content'),
        required=False, initial="", choices=NONCE_CHOICES
    )

    class Meta:
        model = UserContent
        fields = ['usercomponent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.usercomponent.user
        query = UserComponent.objects.filter(user=user)
        self.fields["usercomponent"].queryset = query

        if not self.instance.id:
            self.fields["new_nonce"].initial = INITIAL_NONCE_SIZE
            self.fields["new_nonce"].choices = NONCE_CHOICES[1:]

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


class SpiderAuthForm(AuthenticationForm):
    password = None
    # can authenticate only with SpiderAuthBackend
    # or descendants, so ignore others
    auth_backend = SpiderAuthBackend()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_protections()

    def reset_protections(self):
        self.request.protections = Protection.authall(
            self.request, scope="auth",
            ptype=ProtectionType.authentication.value,
        )
        # here is not even a usercomponent available
        # if this works, something is wrong
        # protections should match username from POST with the ones of the
        # usercomponent (which is available in clean)
        assert(self.request.protections is not True)

    def clean(self):
        username = self.cleaned_data.get('username')
        protection_codes = None
        if self.request.method != "GET" and \
           "protection_codes" in self.request.POST:
            protection_codes = self.request.POST.getlist("protection_codes")

        if username is not None:
            self.user_cache = self.auth_backend.authenticate(
                self.request, username=username,
                protection_codes=protection_codes
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
