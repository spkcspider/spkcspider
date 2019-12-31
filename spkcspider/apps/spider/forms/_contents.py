__all__ = [
    "LinkForm", "TravelProtectionForm", "TravelProtectionManagementForm"
]

from base64 import b64encode
from datetime import timedelta

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from spkcspider.constants import (
    TravelLoginType, VariantType, dangerous_login_choices,
    loggedin_active_tprotections, travel_scrypt_params
)

from ..fields import ContentMultipleChoiceField, MultipleOpenChoiceField
from ..models import AssignedContent, UserComponent
from ..widgets import DatetimePickerWidget, OpenChoiceWidget, SelectizeWidget
from ._messages import login_protection as _login_protection
from ._messages import time_help_text
from .base import DataContentForm

_extra = '' if settings.DEBUG else '.min'

loggedin_active_tprotections_q = models.Q()
for i in loggedin_active_tprotections:
    loggedin_active_tprotections_q |= models.Q(
        associated__info__contains="\x1elogin_protection={}\x1e".format(i)
    )


class LinkForm(DataContentForm):
    content = forms.ModelChoiceField(
        queryset=AssignedContent.objects.filter(
            strength__lte=10
        )
    )
    push = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Improve ranking of this Link.")
    )

    free_fields = {"push": False}

    def __init__(self, uc, request, **kwargs):
        super().__init__(**kwargs)
        # if self.instance.associated:
        #     if "\x1eanchor\x1e" in self.instance.associated:
        #         self.fields["content"].disabled = True
        if self.instance.id:
            self.initial["content"] = \
                self.instance.associated.attached_to_content
        q = self.fields["content"].queryset
        travel = \
            AssignedContent.travelprotections.get_active_for_request(request)
        travel = travel.filter(loggedin_active_tprotections_q)
        self.fields["content"].queryset = q.filter(
            strength__lte=uc.strength
        ).exclude(
            models.Q(usercomponent__travel_protected__in=travel) |
            models.Q(travel_protected__in=travel)
        )
        # component auth should limit links to visible content
        # read access outside from component elsewise possible
        if request.user != uc.user and not request.is_staff:
            q = self.fields["content"].queryset
            self.fields["content"].queryset = q.filter(
                models.Q(usercomponent=uc) |
                models.Q(referenced_by__usercomponent=uc)
            )

    def save(self, commit=True):
        self.instance.associated.attached_to_content = \
            self.cleaned_data["content"]
        return super().save(commit)


class TravelProtectionManagementForm(DataContentForm):

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


class TravelProtectionForm(DataContentForm):
    uc = None
    # self_protection = forms.ChoiceField(
    #    label=_("Self-protection"), help_text=_(_self_protection),
    #     initial="None", choices=PROTECTION_CHOICES
    # )

    active = forms.BooleanField(initial=False, required=False)
    start = forms.DateTimeField(
        required=True, widget=DatetimePickerWidget(),
        help_text=time_help_text
    )
    stop = forms.DateTimeField(
        required=False, widget=DatetimePickerWidget(),
        help_text=time_help_text
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
        widget=SelectizeWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )
    protect_components = forms.ModelMultipleChoiceField(
        queryset=UserComponent.objects.all(), required=False,
        to_field_name="name",
        widget=SelectizeWidget(
            allow_multiple_selected=True,
            attrs={
                "style": "min-width: 250px; width:100%"
            }
        )
    )

    login_protection = forms.ChoiceField(
        choices=TravelLoginType.as_choices(),
        initial=TravelLoginType.hide,
        help_text=_login_protection
    )

    master_pw = forms.CharField(
        label=_("Master Login Password"),
        widget=forms.PasswordInput(render_value=True), required=True,
        help_text=_(
            "Enter Password used for the user account"
        )
    )

    quota_fields = {"trigger_pws": list}

    class Media:
        js = []

    @staticmethod
    def _filter_selfprotection(x):
        if x[0] == TravelLoginType.disable:
            return False
        return True

    @staticmethod
    def _filter_dangerousprotection(x):
        if x[0] in dangerous_login_choices:
            return False
        return True

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.initial["active"] = self.associated.getflag("active")
        if not self.request.user.has_perm(
            "spider_base.use_dangerous_travelprotections"
        ):
            self.fields["login_protection"].choices = \
                filter(
                    self._filter_dangerousprotection,
                    self.fields["login_protection"].choices
                )
        if self.instance.associated.ctype.name == "TravelProtection":
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
            self.fields["login_protection"].choices = \
                filter(
                    self._filter_selfprotection,
                    self.fields["login_protection"].choices
                )
            del self.fields["start"]
            del self.fields["stop"]
        if not getattr(self.instance, "id") and not self.data:
            self.initial["active"] = True

        travel = AssignedContent.travelprotections.get_active_for_request(
            request
        ).filter(loggedin_active_tprotections_q)
        selfid = getattr(self.instance, "id", -1)
        if self.initial["login_protection"] == TravelLoginType.disable:
            self.initial["login_protection"] = \
                TravelLoginType.trigger_disable

        q_component = models.Q(
            user=request.user
        ) & (
            ~models.Q(travel_protected__in=travel) |
            models.Q(travel_protected__id=selfid)
        )
        self.fields["protect_components"].queryset = \
            self.fields["protect_components"].queryset.filter(
                q_component
            ).distinct().order_by(
                "name"
            )

        q_content = models.Q(usercomponent__user=request.user) & (
            ~(
                models.Q(usercomponent__travel_protected__in=travel) |
                models.Q(travel_protected__in=travel) |
                # don't allow detectable contents
                models.Q(info__contains="\x1eanchor\x1e") |
                models.Q(info__contains="\x1eprimary\x1e") |
                # contents also appearing as features are easily detectable
                models.Q(
                    ctype__ctype__contains=VariantType.feature_connect
                )
            ) |
            (
                models.Q(usercomponent__travel_protected__id=selfid) |
                models.Q(travel_protected__id=selfid)
            )
        )
        if getattr(self.instance, "id", None):
            # exlude own content
            q_content &= ~models.Q(pk=self.instance.associated.pk)
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
        if (
            not self.instance.associated.getlist("pwhash", 1) and
            self.instance.associated.ctype.name == "SelfProtection"
        ):
            self.fields["trigger_pws"].required = True
        # use q for filtering (including own)
        self.fields["protect_contents"].queryset = \
            self.fields["protect_contents"].queryset.filter(
                q_content
            ).distinct().order_by(
                "name"
            )

    def clean(self):
        super().clean()
        self.initial["master_pw"] = self.cleaned_data.pop("master_pw", None)
        if not authenticate(
            self.request,
            username=self.instance.associated.usercomponent.username,
            password=self.initial.get("master_pw", None),
            nospider=True
        ):
            self.add_error(
                "master_pw",
                forms.ValidationError(
                    _("Invalid Password"),
                    code="invalid_password"
                )
            )
        if "trigger_pws" in self.cleaned_data:
            pwset = set(map(
                lambda x: b64encode(Scrypt(
                    salt=settings.SECRET_KEY.encode("utf-8"),
                    backend=default_backend(),
                    **travel_scrypt_params
                ).derive(x[:128].encode("utf-8"))).decode("ascii"),
                self.cleaned_data["trigger_pws"]
            ))
            if (
                self.instance.associated.ctype.name == "SelfProtection" and
                self.cleaned_data.get("overwrite_pws") and
                len(pwset) == 0
            ):
                # = passwords are completely empty
                self.add_error("trigger_pws", forms.ValidationError(
                    _(
                        "Empty trigger passwords not allowed "
                        "(for Self-Protection)"
                    )
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

    def get_prepared_attachements(self):
        return {
            "protect_contents":
                list(self.cleaned_data["protect_contents"])
                + [self.instance.associated],
            "protect_components": self.cleaned_data["protect_components"]
        }

    def save(self, commit=True):
        self.instance.approved = bool(self.cleaned_data["approved"])
        return super().save(commit)
