__all__ = [
    "LinkForm", "TravelProtectionForm", "TravelProtectionManagementForm"
]

import json
from base64 import b64encode
from datetime import timedelta as td

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from spkcspider.constants import (
    TravelProtectionType, VariantType, dangerous_login_choices,
    travel_scrypt_params
)

from ..fields import ContentMultipleChoiceField, MultipleOpenChoiceField
from ..models import AssignedContent, AttachedTimespan, UserComponent
from ..queryfilters import loggedin_active_tprotections_q
from ..widgets import (
    ListWidget, OpenChoiceWidget, SelectizeWidget
)
from ._messages import travel_protection as _travel_protection
from ._messages import time_help_text
from .base import DataContentForm

_extra = '' if settings.DEBUG else '.min'


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
        travel = AssignedContent.travel.get_active_for_request(request)
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
        self.instance._prepared_info = "".join(
            map(lambda x: "pwhash={}\x1e".format(x), pwset)
        )
        if self.instance.associated.getflag("anonymous_deactivation"):
            self.instance._prepared_info = \
                "{}anonymous_deactivation\x1e".format(
                    self.instance._prepared_info
                )
        if self.instance.associated.getflag("anonymous_trigger"):
            self.instance._prepared_info = \
                "{}anonymous_trigger\x1e".format(
                    self.instance._prepared_info
                )

        return self.cleaned_data


class TravelProtectionForm(DataContentForm):
    request = None
    pwset = None
    # self_protection = forms.ChoiceField(
    #    label=_("Self-protection"), help_text=_(_self_protection),
    #     initial="None", choices=PROTECTION_CHOICES
    # )

    active = forms.BooleanField(initial=True, required=False)
    timeplans = MultipleOpenChoiceField(
        widget=ListWidget(
            items=[
                {
                    "name": "start",
                    "label": _("Start"),
                    "format_type": "datetime-local",
                    "options": {
                        "flatpickr": {
                            "inline": True,
                            "time_24hr": True,
                            "": "Z"
                        }
                    }
                },
                {
                    "name": "stop",
                    "label": _("Stop"),
                    "format_type": "datetime-local",
                    "options": {
                        "flatpickr": {
                            "inline": True,
                            "time_24hr": True,
                            "": "Z"
                        }
                    }
                }
            ], item_label=_("Timeplan")
        ), required=False,
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

    travel_protection_type = forms.ChoiceField(
        choices=TravelProtectionType.as_choices(),
        initial=TravelProtectionType.hide,
        help_text=_travel_protection
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
        css = {
            "all": [
                "node_modules/flatpickr/dist/flatpickr%s.css" % _extra
            ]
        }
        js = [
            'node_modules/flatpickr/dist/flatpickr%s.js' % _extra
        ]

    def _filter_dangerousprotection(self, x):
        # if it is already selected, still allow selection
        #   elsewise confusing logic and errors
        if (
            x[0] in dangerous_login_choices and
            x[0] != self.initial["travel_protection_type"]
        ):
            return False
        return True

    @staticmethod
    def _filter_selfprotection(x):
        if x[0] == TravelProtectionType.disable:
            return False
        return True

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.request = request
        self.pwset = set()
        associated = self.instance.associated
        self.initial["active"] = associated.getflag("active")
        self.initial["anonymous_deactivation"] = \
            associated.getflag("anonymous_deactivation")

        self.fields["timeplans"].help_text = str(
            self.fields["timeplans"].help_text
        ).format(timezone=timezone.get_current_timezone_name())
        if not getattr(self.instance, "id"):
            now = timezone.now()
            self.initial["travel_protection_type"] = TravelProtectionType.hide
            self.initial["timeplans"] = \
                [
                    json.dumps({
                        "start": (now + td(hours=3)).isoformat(),
                        "stop": (now + td(days=7)).isoformat()
                    })
                ]
        else:
            self.initial["travel_protection_type"] = \
                associated.getlist("travel_protection_type", 1)[0]
            self.initial["timeplans"] = \
                [
                    json.dumps({
                        "start": x.start.isoformat() if x.start else None,
                        "stop": x.stop.isoformat() if x.stop else None
                    }) for x in associated.attachedtimespans.filter(
                        name="active"
                    )
                ]
        if not self.request.user.has_perm(
            "spider_base.use_dangerous_travelprotections"
        ):
            self.fields["travel_protection_type"].choices = \
                filter(
                    self._filter_dangerousprotection,
                    self.fields["travel_protection_type"].choices
                )
        if associated.ctype.name == "SelfProtection":
            self.fields["travel_protection_type"].choices = \
                filter(
                    self._filter_selfprotection,
                    self.fields["travel_protection_type"].choices
                )
            del self.fields["timeplans"]
        if not getattr(self.instance, "id") and not self.data:
            self.initial["active"] = True

        travel = AssignedContent.travel.get_active_for_request(
            request
        ).filter(loggedin_active_tprotections_q)
        selfid = self.instance.id or -1
        q_component = models.Q(
            user=request.user
        ) & (
            ~models.Q(travel_protected__in=travel) |
            models.Q(travel_protected__id=selfid)
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
            q_content &= ~models.Q(pk=associated.pk)
            self.initial["anonymous_deactivation"] = \
                associated.getflag("anonymous_deactivation")
            if associated.getlist("pwhash", 1):
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
            not associated.getlist("pwhash", 1) and
            associated.ctype.name == "SelfProtection"
        ):
            self.fields["trigger_pws"].required = True
        # use q for filtering (including own)
        self.fields["protect_contents"].queryset = \
            self.fields["protect_contents"].queryset.filter(
                q_content
            ).distinct().order_by(
                "name"
            )

        self.fields["protect_components"].queryset = \
            self.fields["protect_components"].queryset.filter(
                q_component
            ).distinct().order_by(
                "name"
            )

    def _clean_timeplan(self, ob):
        if isinstance(ob, str):
            ob = json.loads(ob)
        start = ob.get("start", None)
        if isinstance(start, str):
            start = parse_datetime(start)
        stop = ob.get("stop", None)
        if isinstance(stop, str):
            stop = parse_datetime(stop)
        return AttachedTimespan(
            unique=False,
            name="active",
            start=start,
            stop=stop,
            content=self.instance.associated
        )

    def clean_timeplans(self):
        return list(map(self._clean_timeplan, self.cleaned_data["timeplans"]))

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
            self.pwset = pwset
        else:
            self.pwset = set(self.instance.associated.getlist("pwhash", 20))
        for i in self.cleaned_data["timeplans"]:
            try:
                i.clean()
            except forms.ValidationError as exc:
                self.add_error("timeplans", exc)
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
        ret = {
            "attachedtimespans": self.cleaned_data["timeplans"]
        }
        if self.cleaned_data["travel_protection_type"] not in {
            TravelProtectionType.wipe_user.value,
            TravelProtectionType.trigger_disable_user.value
        }:
            ret["protect_contents"] = \
                [
                    self.instance.associated,
                    *self.cleaned_data["protect_contents"]
                ]
            ret["protect_components"] = \
                list(self.cleaned_data["protect_components"])
        return ret

    def save(self, commit=False):
        self.instance.free_data["is_travel_protected"] = \
            self.request.session.get("is_travel_protected", False)
        # activates _prepared_info
        self.instance._prepared_info = ""
        if self.cleaned_data.get("active"):
            self.instance._prepared_info = \
                "{}active\x1e".format(
                    self.instance._prepared_info
                )
        self.instance._prepared_info = \
            "{}travel_protection_type={}\x1e".format(
                self.instance._prepared_info,
                self.cleaned_data["travel_protection_type"]
            )
        if self.cleaned_data.get("anonymous_deactivation"):
            self.instance._prepared_info = \
                "{}anonymous_deactivation\x1e".format(
                    self.instance._prepared_info
                )
        if self.cleaned_data.get("anonymous_trigger"):
            self.instance._prepared_info = \
                "{}anonymous_trigger\x1e".format(
                    self.instance._prepared_info
                )
        self.instance._prepared_info += "".join(
            map(lambda x: "pwhash={}\x1e".format(x), self.pwset)
        )
        return super().save(commit)
