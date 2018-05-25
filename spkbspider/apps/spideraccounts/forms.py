from django import forms
from django.contrib.auth.forms import (
    UserCreationForm, UserChangeForm, ReadOnlyPasswordHashField
)
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _


class SignupForm(UserCreationForm):
    # real: username, fake for spammers
    name = forms.CharField(
        label="", max_length=100, required=False, widget=forms.HiddenInput()
    )
    # fake for spammers
    email = forms.EmailField(
        label="", max_length=100, required=False, widget=forms.HiddenInput()
    )
    # email, real
    liame = forms.EmailField(
        label=_('email address (optional)'), max_length=100, required=False
    )
    # question = forms.CharField(max_length=100, required=True)
    # question_answer = None

    class Meta:
        model = get_user_model()
        fields = ['username', 'password1', 'password2',
                  'name', 'liame', 'email']

    # def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)
    #    self.question_answer = ""

    def is_valid(self):
        """
        Returns True if the form has no errors. Otherwise, False. If errors are
        being ignored, returns False.
        """
        if self.data['email'] != "" or self.data['name']:
            return False
        return self.is_bound and not self.errors

    def clean(self):
        # clean up email hack
        super(SignupForm, self).clean()
        self.cleaned_data["email"] = self.cleaned_data["liame"]
        del self.cleaned_data["liame"]
        del self.cleaned_data["name"]


class UserUpdateForm(UserChangeForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password, but you can change the password using "
            "<a href=\"../password_change/\">this form</a>."
        ),
    )

    class Meta:
        model = get_user_model()
        fields = ['username', 'email', 'password']
