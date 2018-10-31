from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings


if getattr(settings, "USE_CAPTCHAS", False):
    from captcha.fields import CaptchaField
else:
    CaptchaField = None


class SignupForm(UserCreationForm):
    # TODO: for a better spammer protection, use useragent for seeding
    # and add/rename, move random fields
    # disguise hidden fields
    use_required_attribute = False

    # real: username, fake for simple spammers
    name = forms.CharField(
        label="", max_length=100, required=False, widget=forms.HiddenInput()
    )
    # fake for simple spammers
    email = forms.EmailField(
        label="", max_length=100, required=False, widget=forms.HiddenInput()
    )
    # email, real
    liame = forms.EmailField(
        label=_('Email Address'), max_length=100, required=False,
        help_text=_("(optional)")
    )

    class Meta:
        model = get_user_model()
        fields = ['username', 'password1', 'password2',
                  'name', 'liame', 'email']

    def is_valid(self):
        """
        Returns True if the form has no errors. Otherwise, False. If errors are
        being ignored, returns False.
        """
        if self.data['email'] or self.data['name']:
            return False
        return self.is_bound and not self.errors

    def clean(self):
        # clean up email hack
        super(SignupForm, self).clean()
        self.cleaned_data["email"] = self.cleaned_data["liame"]
        del self.cleaned_data["liame"]
        del self.cleaned_data["name"]


if CaptchaField:
    # add captcha, disguised name
    SignupForm.declared_fields[settings.SPIDER_CAPTCHA_FIELD_NAME] = \
        CaptchaField(label=_("Captcha"))
    SignupForm.base_fields[settings.SPIDER_CAPTCHA_FIELD_NAME] = \
        SignupForm.declared_fields[settings.SPIDER_CAPTCHA_FIELD_NAME]


class UserUpdateForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = get_user_model()
        fields = model.SAFE_FIELDS

    def __init__(self, *args, **kwargs):
        _ = gettext
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['password'].help_text = \
            self.fields['password'].help_text.format(
                reverse('auth:password_change')
            )
        f = self.fields.get('user_permissions')
        if f is not None:
            f.queryset = f.queryset.select_related('content_type')
        self.fields['email'].help_text += _("Optional")
