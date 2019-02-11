"""
User Components/Info
namespace: spider_base

"""

__all__ = [
    "UserComponent", "UserComponentManager", "TokenCreationError",
    "UserInfo"
]

import logging

from django.db import models
from django.conf import settings
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core import validators

from ..helpers import get_settings_func, validator_token, create_b64_id_token
from ..constants import (
    ProtectionType, VariantType, MAX_TOKEN_B64_SIZE, TokenCreationError,
    default_uctoken_duration, force_captcha, index_names, hex_size_of_bigid
)


logger = logging.getLogger(__name__)


_name_help = _(
    "Name of the component.<br/>"
    "Note: there are special named components "
    "with different protection types and scopes.<br/>"
    "Most prominent: \"index\" for authentication"
)


_required_passes_help = _(
    "How many protection must be passed? "
    "Set greater 0 to enable protection based access"
)

_feature_help = _(
    "Appears as featured on \"home\" page"
)


class UserComponentManager(models.Manager):
    def _update_args(self, defaults, kwargs):
        if defaults is None:
            defaults = {}
        if kwargs is None:
            kwargs = defaults
        name = kwargs.get("name", defaults.get("name", None))
        if name in index_names and force_captcha:
            defaults["required_passes"] = 2
            defaults["strength"] = 10
        elif name in index_names:
            defaults["required_passes"] = 1
            defaults["strength"] = 10
        elif kwargs.get("public", defaults.get("public", False)):
            if kwargs.get(
                "required_passes",
                defaults.get("required_passes", 0)
            ) == 0:
                defaults["strength"] = 0
            else:
                defaults["strength"] = 4
        else:
            if kwargs.get(
                "required_passes",
                defaults.get("required_passes", 0)
            ) == 0:
                defaults["strength"] = 5
            else:
                defaults["strength"] = 9
        return defaults

    def create(self, **kwargs):
        ret = self.get_queryset().create(
            **self._update_args(kwargs, None)
        )
        if not ret.token:
            ret.token = create_b64_id_token(ret.id, "/")
            ret.save(update_fields=["token"])
        return ret

    def update_or_create(self, defaults=None, **kwargs):
        ret = self.get_queryset().update_or_create(
            defaults=self._update_args(defaults, kwargs), **kwargs
        )
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "/")
            ret[0].save(update_fields=["token"])
        return ret

    def get_or_create(self, defaults=None, **kwargs):
        ret = self.get_queryset().get_or_create(
            defaults=self._update_args(defaults, kwargs), **kwargs
        )
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "/")
            ret[0].save(update_fields=["token"])
        return ret


class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection and identifier, replaces nonce
    #  16 = usercomponent.id in hexadecimal
    #  +1 for seperator
    token = models.CharField(
        max_length=(MAX_TOKEN_B64_SIZE)+hex_size_of_bigid+2,
        db_index=True, unique=True, null=True, blank=True,
        validators=[
            validator_token
        ]
    )
    public = models.BooleanField(
        default=False,
        help_text=_(
            "Is public? Is listed and searchable?<br/>"
            "Note: This field is maybe not deactivatable "
            "because of assigned content"
        )
    )
    description = models.TextField(
        default="",
        help_text=_(
            "Description of user component."
        ), blank=True
    )
    required_passes = models.PositiveIntegerField(
        default=0,
        help_text=_required_passes_help
    )
    # cached protection strength
    strength = models.PositiveSmallIntegerField(
        default=0,
        validators=[validators.MaxValueValidator(10)],
        editable=False
    )
    # fix linter warning
    objects = UserComponentManager()
    # special name: index, (fake_index):
    #    protections are used for authentication
    #    attached content is only visible for admin and user
    # db_index=True: "index", "fake_index" requests can speed up
    name = models.SlugField(
        max_length=50,
        null=False,
        db_index=True,
        allow_unicode=True,
        help_text=_name_help
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
    )
    features = models.ManyToManyField(
        "spider_base.ContentVariant", related_name="supports", blank=True,
        limit_choices_to=models.Q(
            ctype__contains=VariantType.feature.value
        )
    )
    primary_anchor = models.ForeignKey(
        "spider_base.AssignedContent", related_name="primary_anchor_for",
        null=True, blank=True,
        limit_choices_to={
            "info__contains": "\nanchor\n",
        }, on_delete=models.SET_NULL,
        help_text=_(
            "Select main identyifing anchor. Also used for attaching "
            "persisting tokens (elsewise they are attached to component)"
        )
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    # only admin
    featured = models.BooleanField(default=False, help_text=_feature_help)

    can_auth = models.BooleanField(default=False, editable=False)

    token_duration = models.DurationField(
        default=default_uctoken_duration,
        null=False
    )
    # only editable for admins
    deletion_requested = models.DateTimeField(
        null=True, default=None, blank=True
    )
    contents = None
    # should be used for retrieving active protections, related_name
    protections = None

    class Meta:
        unique_together = [("user", "name")]
        permissions = [("can_feature", "Can feature User Components")]

    def __repr__(self):
        name = self.name
        if name in index_names:
            name = "index"
        return "<UserComponent: %s: %s>" % (self.username, name)

    def get_name(self):
        name = self.name
        if name in index_names:
            name = "index"
        return name

    def __str__(self):
        return self.get_name()

    def clean(self):
        _ = gettext
        self.public = (self.public and self.is_public_allowed)
        self.featured = (self.featured and self.public)
        assert(self.name not in index_names or self.strength == 10)
        assert(self.name in index_names or self.strength < 10)
        obj = self.contents.filter(
            strength__gt=self.strength
        ).order_by("strength").last()
        if obj:
            raise ValidationError(
                _(
                    'Protection strength too low, required: %(strength)s'
                ),
                code="strength",
                params={'strength': obj.strength},
            )

    def auth(self, request, ptype=ProtectionType.access_control.value,
             protection_codes=None, **kwargs):
        AssignedProtection = apps.get_model("spider_base.AssignedProtection")
        return AssignedProtection.authall(
            request, self, ptype=ptype, protection_codes=protection_codes,
            **kwargs
        )

    def get_accumulated_size(self):
        _local_size = 0
        _remote_size = 0
        for elem in self.contents.all():
            if VariantType.feature.value in elem.ctype.ctype:
                _remote_size += elem.get_size()
            else:
                _local_size += elem.get_size()
        return _local_size, _remote_size

    def get_absolute_url(self):
        return reverse(
            "spider_base:ucontent-list",
            kwargs={
                "token": self.token
            }
        )

    @property
    def username(self):
        return getattr(self.user, self.user.USERNAME_FIELD)

    @property
    def user_info(self):
        return self.user.spider_info

    @property
    def index(self):
        return UserComponent.objects.get(user=self.user, name="index")

    @property
    def is_index(self):
        return (self.name in index_names)

    @property
    def is_public_allowed(self):
        """ Can the public attribute be set """
        return self.name not in index_names and not self.contents.filter(
            strength__gte=5
        ).exists()

    @property
    def deletion_period(self):
        return getattr(
            settings, "DELETION_PERIODS_COMPONENTS", {}
        ).get(self.get_name(), None)

    def save(self, *args, **kwargs):
        if self.name in index_names and self.public:
            self.public = False
        super().save(*args, **kwargs)


class UserInfo(models.Model):
    """ Contains generated Informations about user """
    id = models.BigAutoField(primary_key=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False,
        related_name="spider_info",
    )
    allowed_content = models.ManyToManyField(
        "spider_base.ContentVariant", related_name="+", editable=False
    )
    used_space_local = models.BigIntegerField(default=0, editable=False)
    used_space_remote = models.BigIntegerField(default=0, editable=False)

    class Meta:
        default_permissions = []

    def calculate_allowed_content(self):
        from ..contents import installed_contents
        ContentVariant = apps.get_model("spider_base.ContentVariant")
        allowed = []
        cfilterfunc = get_settings_func(
            "ALLOWED_CONTENT_FILTER",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )
        # Content types which are not "installed" should be removed/never used
        for variant in ContentVariant.objects.filter(
            code__in=installed_contents
        ):
            if cfilterfunc(self.user, variant):
                allowed.append(variant)
        # save not required, m2m field
        self.allowed_content.set(allowed)

    def calculate_used_space(self):
        from . import AssignedContent
        self.used_space_local = 0
        self.used_space_remote = 0
        for c in AssignedContent.objects.filter(
            usercomponent__user=self.user
        ):
            if VariantType.feature.value in c.ctype.ctype:
                self.used_space_remote += c.get_size()
            else:
                self.used_space_local += c.get_size()

    def update_with_quota(self, size_diff, quota_type):
        fname = "used_space_{}".format(quota_type)
        qval = getattr(self, fname)
        quota = get_settings_func(
            "SPIDER_GET_QUOTA",
            "spkcspider.apps.spider.functions.get_quota"
        )(self.user, quota_type)
        # if over quota: reducing size is always good and should never fail
        if quota and size_diff > 0 and qval + size_diff > quota:
            raise ValidationError(
                _("Exceeds quota by %(diff)s Bytes"),
                code='quota_exceeded',
                params={'diff': size_diff},
            )
        setattr(
            self, fname, models.F(fname)+size_diff
        )
