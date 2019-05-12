__all__ = [
    "LinkForm", "TravelProtectionForm", "TravelProtectionManagementForm"
]

from datetime import timedelta
from base64 import b64encode

from django import forms
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ..constants import (
    dangerous_login_choices, travel_scrypt_params, TravelLoginType
)
from ..models import LinkContent, TravelProtection, AssignedContent
from ..fields import MultipleOpenChoiceField, ContentMultipleChoiceField
from ..widgets import (
    OpenChoiceWidget, RomeDatetimePickerWidget, Select2Widget
)


_extra = '' if settings.DEBUG else '.min'


_time_help_text = _(
    "Time in \"{}\" timezone"
)


_login_protection = _(
    "Hide: Hide protected contents and components<br/>"
    "Disable: Disable Login temporary<br/>"
    "Hide if triggered: Hide protected contents and components if triggered<br/>"  # noqa: E501
    "Wipe: Wipe protected content on login (maybe not available)<br/>"
    "Wipe User: destroy user on login (maybe not available)<br/><br/>"
    "Note: login protections work only partly on logged in users (just hiding contents and components)"  # noqa: E501
)


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
        travel = TravelProtection.objects.get_active_for_request(request)
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


class TravelProtectionManagementForm(forms.ModelForm):
    class Meta:
        model = TravelProtection
        fields = []

    def clean(self):
        super().clean()
        pwset = set(self.instance.associated.getlist("pwhash", 20))
        self.instance._encoded_form_info = "".join(
            map(lambda x: "pwhash={}\x1e".format(x), pwset)
        )
        if self.instance.associated.getflag("anonymous_deactivation"):
            self.instance._encoded_form_info = \
                "{}anonymous_deactivation\x1e".format(
                    self.instance._encoded_form_info
                )
        if self.instance.associated.getflag("anonymous_trigger"):
            self.instance._encoded_form_info = \
                "{}anonymous_trigger\x1e".format(
                    self.instance._encoded_form_info
                )

        return self.cleaned_data


class TravelProtectionForm(forms.ModelForm):
    uc = None
    # self_protection = forms.ChoiceField(
    #    label=_("Self-protection"), help_text=_(_self_protection),
    #     initial="None", choices=PROTECTION_CHOICES
    # )
    start = forms.DateTimeField(
        required=True, widget=RomeDatetimePickerWidget(),
        help_text=_time_help_text
    )
    stop = forms.DateTimeField(
        required=False, widget=RomeDatetimePickerWidget(),
        help_text=_time_help_text
    )
    trigger_pws = MultipleOpenChoiceField(
        label=_("Trigger Passwords"), required=False,
        widget=OpenChoiceWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )
    overwrite_pws = forms.BooleanField(
        required=False, initial=False,
        help_text=_(
            "If set, the set of passwords is overwritten or "
            "removed (if no passwords are set)"
        )
    )
    anonymous_deactivation = forms.BooleanField(
        required=False, initial=False,
        help_text=_(
            "Can deactivate protection without login"
        )
    )
    protect_contents = ContentMultipleChoiceField(
        queryset=AssignedContent.objects.all(), required=False,
        to_field_name="id",
        widget=Select2Widget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    class Meta:
        model = TravelProtection
        fields = [
            "active", "start", "stop", "login_protection",
            "protect_components", "protect_contents", "trigger_pws"
        ]
        widgets = {
            "protect_components": Select2Widget(
                 allow_multiple_selected=True,
                 attrs={
                     "style": "min-width: 250px; width:100%"
                 }
            )
        }
        help_texts = {
            "login_protection": _login_protection
        }

    class Media:
        js = []

    @staticmethod
    def _filter_travelprotection(x):
        if not getattr(settings, "DANGEROUS_TRAVEL_PROTECTIONS", False):
            if x[0] in dangerous_login_choices:
                return False
        return True

    @classmethod
    def _filter_selfprotection(cls, x):
        if x[0] == TravelLoginType.disable.value:
            return False
        return cls._filter_travelprotection(x)

    def __init__(self, request, uc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uc = uc
        self.request = request
        if self.instance.associated.ctype.name == "TravelProtection":
            filter_func = self._filter_travelprotection
            self.fields["start"].help_text = str(
                self.fields["start"].help_text
            ).format(timezone.get_current_timezone_name())
            self.fields["stop"].help_text = str(
                self.fields["stop"].help_text
            ).format(timezone.get_current_timezone_name())
            if not getattr(self.instance, "id"):
                now = timezone.now()
                self.initial["start"] = now + timedelta(hours=3)
                self.initial["stop"] = now + timedelta(days=7)
        else:
            filter_func = self._filter_selfprotection
            del self.fields["start"]
            del self.fields["stop"]
        if not getattr(self.instance, "id") and not self.data:
            self.initial["active"] = True

        self.fields["login_protection"].choices = \
            filter(filter_func, self.fields["login_protection"].choices)
        travel = TravelProtection.objects.get_active_for_request(request)
        selfid = getattr(self.instance, "id", -1)

        q = models.Q(
            user=self.uc.user
        ) & (
            ~models.Q(
                travel_protected__in=travel
            ) |
            models.Q(
                travel_protected__id=selfid
            )
        )
        self.fields["protect_components"].queryset = \
            self.fields["protect_components"].queryset.filter(
                q
            ).distinct().order_by(
                "name"
            )

        q = models.Q(
            usercomponent__user=self.uc.user
        ) & (
            ~(
                models.Q(usercomponent__travel_protected__in=travel) |
                models.Q(travel_protected__in=travel) |
                # don't allow detectable contents
                models.Q(info__contains="\x1eanchor\x1e") |
                models.Q(info__contains="\x1eprimary\x1e")
            ) |
            (
                models.Q(usercomponent__travel_protected__id=selfid) |
                models.Q(travel_protected__id=selfid)
            )
        )
        if getattr(self.instance, "id", None):
            # exlude own content
            q &= ~models.Q(pk=self.instance.associated.pk)
            self.initial["anonymous_deactivation"] = \
                self.instance.associated.getflag("anonymous_deactivation")
            if self.instance.associated.getlist("pwhash", 1):
                self.fields["trigger_pws"].help_text = _(
                    "<span style='color:red'>Trigger passwords already set."
                    "</span>"
                )
            else:
                self.fields["trigger_pws"].help_text = _(
                    "No trigger passwords set."
                )
                del self.fields["overwrite_pws"]
                if self.instance.associated.ctype.name == "SelfProtection":
                    self.fields["trigger_pws"].required = True
        # use q for filtering (including own)
        self.fields["protect_contents"].queryset = \
            self.fields["protect_contents"].queryset.filter(
                q
            ).distinct().order_by(
                "name"
            )

    def clean(self):
        super().clean()
        if "trigger_pws" in self.cleaned_data:
            pwset = set(map(
                lambda x: b64encode(Scrypt(
                    salt=settings.SECRET_KEY.encode("utf-8"),
                    backend=default_backend(),
                    **travel_scrypt_params
                ).derive(x[:128].encode("utf-8"))).decode("ascii"),
                self.cleaned_data["trigger_pws"][:20]
            ))
            if not self.cleaned_data.get("overwrite_pws") and len(pwset) < 20:
                pwset.update(self.instance.associated.getlist(
                    "pwhash", 20-len(pwset)
                ))
        else:
            pwset = set(self.instance.associated.getlist("pwhash", 20))
        self.instance._encoded_form_info = "".join(
            map(lambda x: "pwhash={}\x1e".format(x), pwset)
        )
        if self.cleaned_data.get("start") and self.cleaned_data.get("stop"):
            if self.cleaned_data["stop"] < self.cleaned_data["start"]:
                self.add_error("start", forms.ValidationError(
                    _("Stop < Start")
                ))
        if self.cleaned_data.get("anonymous_deactivation"):
            self.instance._encoded_form_info = \
                "{}anonymous_deactivation\x1e".format(
                    self.instance._encoded_form_info
                )
        if self.cleaned_data.get("anonymous_trigger"):
            self.instance._encoded_form_info = \
                "{}anonymous_trigger\x1e".format(
                    self.instance._encoded_form_info
                )
        try:
            self.cleaned_data["protect_contents"] = \
                self.cleaned_data["protect_contents"].exclude(
                    usercomponent__in=self.cleaned_data["protect_components"]
                )
        except KeyError:
            pass
        return self.cleaned_data

    def is_valid(self):
        isvalid = super().is_valid()
        if not getattr(self, "cleaned_data", None):
            return False
        return isvalid

    def _save_m2m(self):
        super()._save_m2m()
        self.instance.protect_contents.add(self.instance.associated)
