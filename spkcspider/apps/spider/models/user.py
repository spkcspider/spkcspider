"""
User Components/Info
namespace: spider_base

"""

__all__ = [
    "UserComponent", "UserComponentManager", "TokenCreationError",
    "AuthToken", "UserInfo"
]

import logging

from django.db import models
from django.conf import settings
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.urls import reverse
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core import validators

from ..helpers import token_nonce, get_settings_func
from ..constants import (
    ProtectionType, MAX_NONCE_SIZE, hex_size_of_bigid, TokenCreationError,
    default_uctoken_duration, protected_names, force_captcha, index_names
)


logger = logging.getLogger(__name__)


_name_help = _("""
Name of the component.<br/>
Note: there are special named components
with different protection types and scopes.<br/>
Most prominent: "index" for authentication
""")


_required_passes_help = _(
    "How many protection must be passed? "
    "Set greater 0 to enable protection based access"
)

_feature_help = _(
    "Appears as featured on \"home\" page"
)


class UserComponentManager(models.Manager):
    def get_or_create_component(self, defaults={}, **kwargs):
        try:
            return (self.get_queryset().get(**kwargs), False)
        except ObjectDoesNotExist:
            defaults.update(kwargs)
            if defaults["name"] in index_names and force_captcha:
                defaults["required_passes"] = 2
                defaults["strength"] = 10
            elif self.name in index_names:
                defaults["required_passes"] = 1
                defaults["strength"] = 10
            elif defaults["public"]:
                defaults["strength"] = 5
            else:
                defaults["strength"] = 0
            return (self.create(**defaults), True)


class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3,
        db_index=False
    )
    public = models.BooleanField(
        default=False,
        help_text=_(
            "Is public? Can be searched?<br/>"
            "Note: Field is maybe blocked by assigned content"
        )
    )
    description = models.TextField(
        default="",
        help_text=_(
            "Description of user component. Visible if \"public\"."
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
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    # only admin
    featured = models.BooleanField(default=False, help_text=_feature_help)

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

    def __str__(self):
        name = self.name
        if name in index_names:
            name = "index"
        return name

    def clean(self):
        _ = gettext
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

    def get_size(self):
        size_ = 0
        for elem in self.contents.all():
            size_ += elem.get_size()
        return size_

    def get_absolute_url(self):
        return reverse(
            "spider_base:ucontent-list",
            kwargs={
                "id": self.id, "nonce": self.nonce
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
    def name_protected(self):
        """ Is it allowed to change the name """
        return self.name in protected_names

    @property
    def no_public(self):
        """ Can the usercomponent be turned public """
        return self.name in index_names or self.contents.filter(
            strength__gte=5
        )

    def save(self, *args, **kwargs):
        if self.name in index_names and self.public:
            self.public = False
        super().save(*args, **kwargs)


class AuthToken(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    usercomponent = models.ForeignKey(
        UserComponent, on_delete=models.CASCADE,
        related_name="authtokens"
    )
    created_by_special_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="+", blank=True, null=True
    )
    session_key = models.CharField(max_length=40, null=True)
    # brute force protection
    #  16 = usercomponent.id in hexadecimal
    token = models.SlugField(
        max_length=(MAX_NONCE_SIZE*4//3)+hex_size_of_bigid,
        db_index=True
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        unique_together = [
            ("usercomponent", "token")
        ]

    def create_auth_token(self):
        self.token = "{}_{}".format(
            hex(self.usercomponent.id)[2:],
            token_nonce(getattr(settings, "TOKEN_SIZE", 30))
        )

    def save(self, *args, **kwargs):
        for i in range(0, 1000):
            if i >= 999:
                raise TokenCreationError(
                    'A possible infinite loop was detected'
                )
            self.create_auth_token()
            try:
                self.validate_unique()
                break
            except ValidationError:
                pass
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
    used_space = models.BigIntegerField(default=0, editable=False)

    class Meta:
        default_permissions = []

    def calculate_allowed_content(self):
        ContentVariant = apps.get_model("spider_base.ContentVariant")
        allowed = []
        cfilterfunc = get_settings_func(
            "ALLOWED_CONTENT_FILTER",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )
        for variant in ContentVariant.objects.all():
            if cfilterfunc(self.user, variant):
                allowed.append(variant)
        # save not required, m2m field
        self.allowed_content.set(allowed)

    def update_used_space(self):
        size_ = 0
        for u in self.user.usercomponent_set.all():
            size_ += u.get_size()
        self.used_space = size_

    def update_quota(self, size_diff):
        quota = getattr(settings, "FIELDNAME_QUOTA", None)
        if quota:
            quota = getattr(self.user, quota, None)
        if not quota:
            quota = getattr(settings, "DEFAULT_QUOTA_USER", None)
        if quota and self.used_space + size_diff > quota:
            return ValidationError(
                _("Exceeds quota by %(diff)s Bytes"),
                code='quota_exceeded',
                params={'diff': size_diff},
            )
        else:
            self.used_space += size_diff
            self.save()
