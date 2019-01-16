__all__ = [
    "SpiderAuthForm"
]


from django import forms
from django.contrib.auth.forms import AuthenticationForm

from ..auth import SpiderAuthBackend
from ..constants import ProtectionType

from ..models import (
    Protection
)


class SpiderAuthForm(AuthenticationForm):
    password = None
    # can authenticate only with specialized backend(s) so ignore others
    auth_backend = SpiderAuthBackend()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
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
        assert type(self.request.protections) is not int,\
            "login evaluates to success without data"

    def clean(self):
        username = self.cleaned_data.get('username')
        protection_codes = None
        if "protection" in self.request.GET:
            protection_codes = self.request.GET.getlist("protection")

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
