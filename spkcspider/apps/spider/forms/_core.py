__all__ = ["UserComponentForm", "UserContentForm"]

import logging

from django import forms
from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS
from django.db import models
from django.utils.translation import gettext_lazy as _

from spkcspider.constants import (
    MIN_PROTECTION_STRENGTH_LOGIN, ProtectionType, VariantType, protected_names
)
from spkcspider.utils.security import (
    calculate_protection_strength, create_b64_id_token
)

from ..conf import INITIAL_STATIC_TOKEN_SIZE, STATIC_TOKEN_CHOICES
from ..models import (
    AssignedContent, AuthToken, ContentVariant, Protection, UserComponent
)
from ._messages import (
    help_text_features_components, help_text_features_contents,
    help_text_static_token
)

logger = logging.getLogger(__name__)


class UserComponentForm(forms.ModelForm):
    protections = None
    request = None
    new_static_token = forms.ChoiceField(
        label=_("New static token"), help_text=help_text_static_token,
        required=False, initial="", choices=STATIC_TOKEN_CHOICES
    )

    master_pw = forms.CharField(
        label=_("Master Password"),
        widget=forms.PasswordInput(
            render_value=True,
            attrs={
                "autocomplete": "off"
            }
        ), required=False,
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
            'features': help_text_features_components,
        }
        widgets = {
            'features': forms.CheckboxSelectMultiple(),
            'default_content_features': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(
                attrs={
                    "maxlength": settings.SPIDER_MAX_DESCRIPTION_LENGTH+1
                }
            ),
            # 'primary_anchor': SelectizeWidget(
            #    allow_multiple_selected=False,
            #    attrs={
            #        "style": "min-width: 150px; width:100%"
            #    }
            # ),
        }

    class Media:
        js = [
            'spider_base/UserComponent.js'
        ]

    def __init__(self, request, data=None, files=None, auto_id='id_%s',
                 prefix=None, *args, **kwargs):
        super().__init__(
            *args, data=data, files=files, auto_id=auto_id,
            prefix=prefix, **kwargs
        )
        self.request = request
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
            self.fields["features"].queryset.exclude(
                models.Q(ctype__contains=VariantType.feature_connect) |
                models.Q(name="DomainMode") |
                models.Q(name="DefaultActions")
            ) &
            request.user.spider_info.allowed_content.all()
        ).order_by("name")

        self.fields["default_content_features"].queryset = (
            self.fields["default_content_features"].queryset.exclude(
                name="DomainMode"
            ) &
            request.user.spider_info.allowed_content.all()
        ).order_by("name")

        if self.instance.is_index:
            assert self.instance.id
            ptype = ProtectionType.authentication
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
        else:
            ptype = ProtectionType.access_control

        self.protections = Protection.get_forms(
            data=data, files=files, prefix=prefix, uc=self.instance,
            ptype=ptype, request=request, form=self
        )
        self.protections = list(self.protections)

        if self.instance.id:
            # data and files field maybe not filled (to load from component)
            # remove pw if index because it is used for legitimating changes
            if not self.instance.is_index:
                self.initial["master_pw"] = \
                    self.fields["master_pw"].widget.value_from_datadict(
                        request.POST, request.FILES,
                        self.add_prefix("master_pw")
                    )
            if self.instance.name in protected_names:
                self.fields["name"].disabled = True
            if not self.instance.is_public_allowed:
                self.fields["public"].disabled = True
                self.fields.pop("featured", None)
            self.fields["primary_anchor"].queryset = \
                self.fields["primary_anchor"].queryset.filter(
                    usercomponent=self.instance
                )
        else:
            self.fields.pop("primary_anchor", None)
            self.fields["new_static_token"].choices = \
                self.fields["new_static_token"].choices[1:]
            self.fields["new_static_token"].initial = INITIAL_STATIC_TOKEN_SIZE
            self.fields["required_passes"].initial = 1

    @property
    def media(self):
        """Return all media required to render the widgets on this form."""
        media = super().media + forms.Media(self.Media)
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

    def clean(self):
        ret = super().clean()
        assert(self.instance.user)
        self.cleaned_data["can_auth"] = False
        self.initial["master_pw"] = self.cleaned_data.pop("master_pw", None)
        if 'name' not in self.cleaned_data:
            # ValidationError so return, calculations won't work here
            return

        if not self.instance.id:
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
            assert protection.cleaned_data["state"], "no valid state"
        prot_strength, max_prot_strength = \
            calculate_protection_strength(
                self.cleaned_data["required_passes"],
                self.instance.id and self.protections
            )

        self.cleaned_data["strength"] = 0
        if self.cleaned_data["name"] == "index":
            if prot_strength < MIN_PROTECTION_STRENGTH_LOGIN:
                self.add_error(None, forms.ValidationError(
                    _("Login requires higher strength: %(strength)s"),
                    code="insufficient_strength_login",
                    params={"strength": MIN_PROTECTION_STRENGTH_LOGIN}
                ))
                self.add_error("required_passes", forms.ValidationError(
                    _(
                        "Login requires higher strength, consider increasing "
                        "required_passes"
                    )
                ))
            self.cleaned_data["strength"] = 10
            return ret
        if not self.cleaned_data["public"]:
            self.cleaned_data["strength"] += 5
        # check on creation
        if prot_strength is None and self.cleaned_data["required_passes"] > 0:
            self.cleaned_data["strength"] += 4
        self.cleaned_data["strength"] += prot_strength or 0
        self.cleaned_data["can_auth"] = max_prot_strength >= 4

        if self.instance.id:
            f = self.instance.features.filter(
                (
                    models.Q(
                        ctype__contains=VariantType.component_feature
                    ) &
                    models.Q(
                        ctype__contains=VariantType.feature_connect
                    )
                ) |
                models.Q(name="DomainMode") |
                models.Q(name="DefaultActions")
            ) & self.request.user.spider_info.allowed_content.all()

            self.cleaned_data["features"] = ContentVariant.objects.filter(
                models.Q(id__in=f.values_list("id", flat=True)) |
                models.Q(
                    id__in=self.cleaned_data["features"]
                    .values_list("id", flat=True)
                )
            )

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
            # executes clean
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
        return super().save(commit=commit)
    save.alters_data = True


class UserContentForm(forms.ModelForm):
    prefix = "content_control"
    new_static_token = forms.ChoiceField(
        label=_("New static token"), help_text=help_text_static_token,
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
            'features': help_text_features_contents,
        }
        widgets = {
            # 'usercomponent': SelectizeWidget(
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
        self.initial["usercomponent"] = self.instance.usercomponent
        self.fields["usercomponent"].required = False
        setattr(self.fields["usercomponent"], "spkc_use_uriref", False)
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

        travel = AssignedContent.travel.get_active_for_request(
            request
        )
        query = UserComponent.objects.filter(
            user=user, strength__gte=self.instance.ctype.strength
        ).exclude(travel_protected__in=travel)
        self.fields["usercomponent"].queryset = query

        if VariantType.feature_connect in self.instance.ctype.ctype:
            self.fields["usercomponent"].disabled = True
            self.fields["usercomponent"].help_text = _(
                "Features cannot move between components"
            )

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
                        ctype__contains=VariantType.persist
                    )
            user = request.user
            if not user.is_authenticated:
                user = self.instance.usercomponent.user
            self.fields["features"].queryset = (
                self.fields["features"].queryset &
                user.spider_info.allowed_content.all() &
                self.instance.ctype.valid_features.all()
            ).exclude(name="DomainMode").order_by("name")
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
        if not self.cleaned_data.get("usercomponent"):
            self.cleaned_data["usercomponent"] = self.initial["usercomponent"]

        # check here if the user is allowed to create the instance
        #   updates are always possible
        if (
            not self.instance.id and
            not self.cleaned_data["usercomponent"].user_info.allowed_content.filter(  # noqa: E501
                name=self.instance.ctype.name
            ).exists()
        ):
            raise forms.ValidationError(
                message=_('Not an allowed ContentVariant for this user'),
                code='disallowed_contentvariant'
            )
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
            if self.cleaned_data["features"].filter(
                ctype__contains=VariantType.domain_mode
            ).exists():
                # fixes strange union bug
                self.cleaned_data["features"] = ContentVariant.objects.filter(
                    models.Q(name="DomainMode") |
                    models.Q(
                        id__in=self.cleaned_data["features"].values_list(
                            "id", flat=True
                        )
                    )
                )
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

            AssignedContent.objects.filter(
                attached_to_token__in=tokens
            ).update(usercomponent=self.instance.usercomponent)
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
        if self.cleaned_data.get("new_static_token", ""):
            self.instance.token_generate_new_size = \
                int(self.cleaned_data["new_static_token"])
        elif not self.instance.token:
            self.instance.token_generate_new_size = \
                self.fields["new_static_token"].initial
        return super().save(commit=commit)
    save.alters_data = True
