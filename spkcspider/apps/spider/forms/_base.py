__all__ = ["UserComponentForm", "UserContentForm"]

import logging
from statistics import mean

from django.conf import settings
from django import forms
from django.db import models
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.translation import gettext_lazy as _

from ..models import (
    Protection, UserComponent, AssignedContent, ContentVariant, AuthToken,
    TravelProtection
)

from ..helpers import create_b64_id_token
from ..constants import (
    ProtectionType, VariantType, protected_names, MIN_PROTECTION_STRENGTH_LOGIN
)
from ..conf import STATIC_TOKEN_CHOICES, INITIAL_STATIC_TOKEN_SIZE
from ..signals import move_persistent
# from ..widgets import Select2Widget

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


_help_text_features_components = _("""
Features which should be active on component and user content<br/>
Note: persistent Features (=features which use a persistent token) require and enable "Persistence"
""")  # noqa: E501

_help_text_features_contents = _("""
Features which should be active on user content<br/>
Note: persistent Features (=features which use a persistent token) require the active "Persistence" Feature on usercomponent. They are elsewise excluded.
""")  # noqa: E501


class UserComponentForm(forms.ModelForm):
    protections = None
    new_static_token = forms.ChoiceField(
        label=_("New static token"), help_text=_help_text_static_token,
        required=False, initial="", choices=STATIC_TOKEN_CHOICES
    )

    master_pw = forms.CharField(
        label=_("Master Password"),
        widget=forms.PasswordInput(render_value=True), required=False,
        help_text=_(
            "If you don't set a password the unlocking may fail "
            "in future (change of server secrets)"
        )
    )

    class Meta:
        model = UserComponent
        fields = [
            'name', 'description', 'public', 'featured',
            'features', 'default_content_features',
            'primary_anchor', 'required_passes', 'token_duration'
        ]
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _('Name of User Component already exists')
            }
        }
        help_texts = {
            'features': _help_text_features_components,
        }
        widgets = {
            'features': forms.CheckboxSelectMultiple(),
            'default_content_features': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(
                attrs={
                    "maxlength": settings.SPIDER_MAX_DESCRIPTION_LENGTH+1
                }
            ),
            # 'primary_anchor': Select2Widget(
            #    allow_multiple_selected=False,
            #    attrs={
            #        "style": "min-width: 150px; width:100%"
            #    }
            # ),

        }

    def __init__(self, request, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        # self.fields["allow_domain_mode"].disabled = True
        self.fields["new_static_token"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_static_token"].choices
        )
        if not (
            request.user.is_superuser or
            request.user.has_perm('spider_base.can_feature')
        ) or request.session.get("is_travel_protected", False):
            self.fields['featured'].disabled = True

        self.fields["features"].queryset = (
            self.fields["features"].queryset &
            request.user.spider_info.allowed_content.all()
        ).order_by("name")

        self.fields["default_content_features"].queryset = (
            self.fields["default_content_features"].queryset &
            request.user.spider_info.allowed_content.all()
        ).order_by("name")

        # data and files field maybe not filled (to load from component)
        # remove pw if index because it is used for legitimating changes
        if getattr(self.instance, "id", None) and not self.instance.is_index:
            self.initial["master_pw"] = \
                self.fields["master_pw"].widget.value_from_datadict(
                    request.POST, request.FILES,
                    self.add_prefix("master_pw")
                )

        if self.instance.id:
            if self.instance.name in protected_names:
                self.fields["name"].disabled = True
            if not self.instance.is_public_allowed:
                self.fields["public"].disabled = True
                self.fields.pop("featured", None)
            self.fields["primary_anchor"].queryset = \
                self.fields["primary_anchor"].queryset.filter(
                    usercomponent=self.instance
                )
            if self.instance.is_index:
                self.fields["master_pw"].required = True
                self.fields["master_pw"].label = _(
                    "Master Login Password"
                )
                self.fields["master_pw"].help_text = _(
                    "Enter Password used for user account<br/>"
                    "Note: to migrate data, first enter old password then the "
                    "new one"
                )
                self.fields.pop("features", None)
                self.fields.pop("featured", None)
                self.fields["required_passes"].help_text = _(
                    "How many protections must be passed to login?<br/>"
                    "Minimum is 1, no matter what selected"
                )
                ptype = ProtectionType.authentication.value
            else:

                ptype = ProtectionType.access_control.value
            self.protections = Protection.get_forms(
                data=data, files=files, prefix=prefix, uc=self.instance,
                ptype=ptype, request=request, form=self
            )
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

    def clean_description(self):
        value = self.cleaned_data.get("description", "").strip()
        if len(value) > settings.SPIDER_MAX_DESCRIPTION_LENGTH:
            return "{}…".format(
                value[:settings.SPIDER_MAX_DESCRIPTION_LENGTH]
            )
        return value

    def calc_protection_strength(self):
        prot_strength = None
        max_prot_strength = 0
        if getattr(self.instance, "id", None):
            # instant fail strength
            fail_strength = 0
            # regular protections strength
            amount_regular = 0
            strengths = []
            for protection in self.protections:
                if not protection.cleaned_data.get("active", False):
                    continue
                if not protection.is_valid():
                    continue

                if len(str(protection.cleaned_data)) > 100000:
                    raise forms.ValidationError(
                        _("Protection >100 kb: %(name)s"),
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
                    # avg strength but maximal 3,
                    # (4 can appear because of component auth)
                    # clamp
                    strengths = min(round(mean(
                        strengths[:self.cleaned_data["required_passes"]]
                    )), 3)
            else:
                strengths = 0
            prot_strength = max(strengths, fail_strength)

        return (prot_strength, max_prot_strength)

    def clean(self):
        ret = super().clean()
        assert(self.instance.user)
        self.cleaned_data["can_auth"] = False
        self.cleaned_data["allow_domain_mode"] = False
        self.initial["master_pw"] = self.cleaned_data.pop("master_pw", None)
        if 'name' not in self.cleaned_data:
            # ValidationError so return, calculations won't work here
            return

        if not getattr(self.instance, "id", None):
            quota = self.instance.get_component_quota()
            if quota and UserComponent.objects.filter(
                user=self.instance.user
            ).count() >= quota:
                raise forms.ValidationError(
                    _("Maximal amount of usercomponents reached %(amount)s."),
                    code='quota_exceeded',
                    params={'amount': quota},
                )
            # TODO: cleanup into protected_names/forbidden_names
            if self.cleaned_data['name'] in protected_names:
                raise forms.ValidationError(
                    _('Forbidden Name'),
                    code="forbidden_name"
                )

        for protection in self.protections:
            protection.full_clean()
        prot_strength, max_prot_strength = self.calc_protection_strength()

        self.cleaned_data["strength"] = 0
        if self.cleaned_data["name"] == "index":
            if prot_strength < MIN_PROTECTION_STRENGTH_LOGIN:
                self.add_error(None, forms.ValidationError(
                    _("Login requires higher strength: %(strength)s"),
                    code="insufficient_strength_login",
                    params={"strength": MIN_PROTECTION_STRENGTH_LOGIN}
                ))
            self.cleaned_data["strength"] = 10
            return ret
        if not self.cleaned_data["public"]:
            self.cleaned_data["strength"] += 5
            self.cleaned_data["strength"] += prot_strength or 0
        else:
            # check on creation
            if self.cleaned_data["required_passes"] > 0:
                self.cleaned_data["strength"] += 4
        self.cleaned_data["can_auth"] = max_prot_strength >= 4
        if any(map(
            lambda x: VariantType.persist.value in x.ctype,
            self.cleaned_data["features"]
        )):
            # fixes strange union bug
            self.cleaned_data["features"] = ContentVariant.objects.filter(
                models.Q(name="Persistence") |
                models.Q(
                    id__in=self.cleaned_data["features"].values_list(
                        "id", flat=True
                    )
                )
            )
        self.cleaned_data["allow_domain_mode"] = any(map(
            lambda x: VariantType.domain_mode.value in x.ctype,
            self.cleaned_data["features"]
        ))
        min_strength = self.cleaned_data["features"].filter(
            strength__gt=self.cleaned_data["strength"]
        ).aggregate(m=models.Max("strength"))["m"]
        # min_strength is None if no features require a higher strength
        # than provided
        if min_strength:
            self.add_error("features", forms.ValidationError(
                _(
                    "selected features require "
                    "higher protection strength: %(strength)s"
                ),
                code="insufficient_strength",
                params={"strength": min_strength}
            ))
        return self.cleaned_data

    def _save_protections(self):
        for protection in self.protections:
            if not protection.is_valid():
                continue
            protection.save()

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
                self.instance.id, "_",
                int(self.cleaned_data["new_static_token"])
            )
            self.instance.save(update_fields=["token"])

    def save(self, commit=True):
        self.instance.strength = self.cleaned_data["strength"]
        self.instance.can_auth = self.cleaned_data["can_auth"]
        # field maybe not available
        self.instance.allow_domain_mode = \
            self.cleaned_data["allow_domain_mode"]
        return super().save(commit=commit)
    save.alters_data = True


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
        fields = ['usercomponent', 'features', 'name', 'description']
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': _(
                    "Unique Content already exists"
                )
            }
        }
        help_texts = {
            'features': _help_text_features_contents,
        }
        widgets = {
            # 'usercomponent': Select2Widget(
            #     allow_multiple_selected=False,
            #     attrs={
            #         "style": "min-width: 150px; width:100%"
            #     }
            # ),
            'features': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(
                attrs={
                    "maxlength": settings.SPIDER_MAX_DESCRIPTION_LENGTH+1
                }
            )

        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.content.expose_name:
            self.fields["name"].widget = forms.HiddenInput()
        elif self.instance.content.expose_name == "force":
            self.fields["name"].required = True
        if not self.instance.content.expose_description:
            self.fields["description"].widget = forms.HiddenInput()

        self.fields["new_static_token"].choices = map(
            lambda c: (c[0], c[1].format(c[0])),
            self.fields["new_static_token"].choices
        )
        user = self.instance.usercomponent.user

        travel = TravelProtection.objects.get_active_for_request(request)

        query = UserComponent.objects.filter(
            user=user, strength__gte=self.instance.ctype.strength
        ).exclude(travel_protected__in=travel)
        self.fields["usercomponent"].queryset = query

        if self.instance.content.force_token_size:
            sforced = [
                ("", ""),
                (
                    str(self.instance.content.force_token_size),
                    _("New ({})").format(
                        self.instance.content.force_token_size
                    )
                )
            ]

        show_primary_anchor_mig = False
        if self.instance.id:
            if (
                request.user == user and
                self.instance.primary_anchor_for.exists()
            ):
                # can only migrate if a) created, b) real user
                show_primary_anchor_mig = True
            if self.instance.content.force_token_size:
                self.fields["new_static_token"].choices = sforced
        else:
            if self.instance.content.force_token_size:
                self.fields["new_static_token"].initial = \
                    self.instance.content.force_token_size
                self.fields["new_static_token"].choices = sforced[1:]
            else:
                self.fields["new_static_token"].initial = \
                    INITIAL_STATIC_TOKEN_SIZE
                self.fields["new_static_token"].choices = \
                    self.fields["new_static_token"].choices[1:]

        if self.instance.usercomponent.is_index:
            # contents in index has no features as they could allow
            # remote access
            self.fields.pop("features", None)
        else:
            if not self.instance.usercomponent.features.filter(
                name="Persistence"
            ):
                self.fields["features"].queryset = \
                    self.fields["features"].queryset.exclude(
                        ctype__contains=VariantType.persist.value
                    )
            user = request.user
            if not user.is_authenticated:
                user = self.instance.usercomponent.user
            self.fields["features"].queryset = (
                self.fields["features"].queryset &
                user.spider_info.allowed_content.all() &
                self.instance.ctype.valid_features.all()
            ).order_by("name")
            self.fields["features"].initial = (
                self.instance.usercomponent.default_content_features.all() &
                self.instance.ctype.valid_features.all()
            )

        if request.user != user and not request.is_staff:
            del self.fields["usercomponent"]

        if not show_primary_anchor_mig:
            del self.fields["migrate_primary_anchor"]

    def clean_description(self):
        value = self.cleaned_data.get("description", "")
        if not self.instance.content.expose_description:
            return value
        value = value.strip()
        if len(value) > settings.SPIDER_MAX_DESCRIPTION_LENGTH:
            return "{}…".format(
                value[:settings.SPIDER_MAX_DESCRIPTION_LENGTH]
            )
        return value

    def clean(self):
        super().clean()
        self.cleaned_data["allow_domain_mode"] = \
            VariantType.domain_mode.value in self.instance.ctype.ctype
        if "features" in self.cleaned_data:
            min_strength = self.cleaned_data["features"].filter(
                strength__gt=self.instance.usercomponent.strength
            ).aggregate(m=models.Max("strength"))["m"]
            # min_strength is None if no features require a higher strength
            # than provided
            if min_strength:
                self.add_error("features", forms.ValidationError(
                    _(
                        "selected features require "
                        "higher protection strength: %s"
                    ) % min_strength,
                    code="insufficient_strength"
                ))
            if not self.cleaned_data["allow_domain_mode"]:
                self.cleaned_data["allow_domain_mode"] = any(map(
                    lambda x: VariantType.domain_mode.value in x.ctype,
                    self.cleaned_data["features"]
                ))
        return self.cleaned_data

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
        update_fields = set()
        if not self.instance.name:

            update_fields.add("name")
        if self.instance.token_generate_new_size is not None:
            if self.instance.token:
                print(
                    "Old nonce for Content id:", self.instance.id,
                    "is", self.instance.token
                )
            self.instance.token = create_b64_id_token(
                self.instance.id,
                "_",
                self.instance.token_generate_new_size
            )
            self.instance.token_generate_new_size = None
            update_fields.add("token")
        if update_fields:
            self.instance.save(update_fields=update_fields)

    def save(self, commit=True):
        # field maybe not available
        self.instance.allow_domain_mode = \
            self.cleaned_data["allow_domain_mode"]
        if self.cleaned_data.get("new_static_token", ""):
            self.instance.token_generate_new_size = \
                int(self.cleaned_data["new_static_token"])
        elif not self.instance.token:
            self.instance.token_generate_new_size = \
                self.fields["new_static_token"].initial
        return super().save(commit=commit)
    save.alters_data = True
