"""
User Components/Info
namespace: spider_base

"""

__all__ = [
    "UserComponent", "TokenCreationError", "AuthToken", "protected_names",
    "UserInfo"
]

import logging
import datetime

from django.db import models
from django.conf import settings
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core import validators

from ..helpers import token_nonce, MAX_NONCE_SIZE, get_settings_func
from ..constants import ProtectionType

force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)

# require USE_CAPTCHAS
force_captcha = (force_captcha and getattr(settings, "USE_CAPTCHAS", False))

logger = logging.getLogger(__name__)
protected_names = ["index", "fake_index"]

hex_size_of_bigid = 16

default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)


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


class TokenCreationError(Exception):
    pass


class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3
    )
    public = models.BooleanField(
        default=False,
        help_text="Is public? Can be searched?<br/>"
                  "Note: Field is maybe blocked by assigned content"
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
    objects = models.Manager()
    # special name: index:
    #    protections are used for authentication
    #    attached content is only visible for admin and user
    name = models.SlugField(
        max_length=50,
        null=False,
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
        if name == "fake_index":
            name = "index"
        return "<UserComponent: %s: %s>" % (self.username, name)

    def __str__(self):
        name = self.name
        if name == "fake_index":
            name = "index"
        return name

    def _get_default_amount(self):
        if self.name in ("index", "fake_index") and force_captcha:
            return 2
        elif self.name in ("index", "fake_index"):
            return 1
        else:
            return 0  # protections are optional

    def _get_default_strength(self):
        if self.name in ("index", "fake_index"):
            return 10
        elif not self.public:
            return 5
        else:
            return 0

    def clean(self):
        _ = gettext
        self.required_passes = self._get_default_amount()
        self.strength = self._get_default_strength()
        assert(self.name not in ("index", "fake_index") or self.strength == 10)
        assert(self.name in ("index", "fake_index") or self.strength < 10)
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
    def name_protected(self):
        """ Is it allowed to change the name """
        return self.name in protected_names

    @property
    def no_public(self):
        """ Can the usercomponent be turned public """
        return self.name in ("index", "fake_index") or self.contents.filter(
            strength__gte=5
        )

    def save(self, *args, **kwargs):
        if self.name in ("index", "fake_index") and self.public:
            self.public = False
        super().save(*args, **kwargs)


class AuthToken(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    usercomponent = models.ForeignKey(
        UserComponent, on_delete=models.CASCADE,
        related_name="authtokens"
    )
    session_key = models.CharField(max_length=40, null=True)
    # brute force protection
    #  16 = usercomponent.id in hexadecimal
    token = models.SlugField(
        max_length=(MAX_NONCE_SIZE*4//3)+hex_size_of_bigid
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        unique_together = [
            ("usercomponent", "token")
        ]

    def create_auth_token(self):
        self.token = "{}_{}".format(
            hex(self.usercomponent.id)[2:],
            token_nonce()
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

    def update_quota(self, size_diff):
        quota = getattr(settings, "FIELDNAME_QUOTA", None)
        if quota:
            quota = getattr(self.user, quota, None)
        if not quota:
            quota = getattr(settings, "DEFAULT_QUOTA_USER", None)
        if quota and self.used_space + size_diff > quota:
            raise ValidationError(
                _("Exceeded quota by %(diff)s Bytes"),
                code='quota_exceeded',
                params={'diff': size_diff},
            )
        else:
            self.used_space += size_diff
            self.save()
