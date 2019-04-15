"""
Base for Contents
namespace: spider_base

"""

__all__ = [
    "ContentVariant", "AssignedContent"
]

import logging

from django.db import models
from django.utils.translation import gettext, gettext_lazy as _
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core import validators

from ..contents import installed_contents
from ..protections import installed_protections

# from ..constants import VariantType
from ..helpers import validator_token, create_b64_id_token
from ..constants import (
    MAX_TOKEN_B64_SIZE, VariantType, hex_size_of_bigid
)
from ..validators import content_name_validator

from .base import BaseInfoModel

logger = logging.getLogger(__name__)


# ContentType is already occupied
class ContentVariant(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # usercontent abilities/requirements
    ctype = models.CharField(
        max_length=10, default="",
    )
    code = models.CharField(max_length=255)
    name = models.SlugField(max_length=50, unique=True, db_index=True)
    # required protection strength (selection)
    strength = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(10)]
    )

    @property
    def installed_class(self):
        return installed_contents[self.code]

    @property
    def feature_urls(self):
        return installed_contents[self.code].cached_feature_urls(self.name)

    def localize_name(self):
        if self.code not in installed_protections:
            return self.name
        return self.installed_class.localize_name(self.name)

    @property
    def unique_for_component(self):
        return VariantType.unique.value in self.ctype

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<ContentVariant: %s>" % self.__str__()


class UserContentManager(models.Manager):

    def create(self, **kwargs):
        ret = self.get_queryset().create(**kwargs)
        if not ret.token:
            ret.token = create_b64_id_token(ret.id, "/")
            ret.save(update_fields=["token"])
        return ret

    def update_or_create(self, **kwargs):
        ret = self.get_queryset().update_or_create(**kwargs)
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "/")
            ret[0].save(update_fields=["token"])
        return ret

    def get_or_create(self, defaults=None, **kwargs):
        ret = self.get_queryset().get_or_create(**kwargs)
        if not ret[0].token:
            ret[0].token = create_b64_id_token(ret[0].id, "/")
            ret[0].save(update_fields=["token"])
        return ret


class AssignedContent(BaseInfoModel):
    id = models.BigAutoField(primary_key=True, editable=False)
    # fake_level = models.PositiveIntegerField(null=False, default=0)
    attached_to_token = models.ForeignKey(
        "spider_base.AuthToken", blank=True, null=True,
        on_delete=models.CASCADE
    )
    # don't use extensive recursion,
    # this can cause performance problems and headaches
    # this is not enforced for allowing some small chains
    # see SPIDER_MAX_EMBED_DEPTH setting for limits (default around 5)
    attached_to_content = models.ForeignKey(
        "self", blank=True, null=True,
        related_name="attached_contents", on_delete=models.CASCADE
    )
    allow_domain_mode = models.BooleanField(default=False)
    # set to indicate creating a new token
    token_generate_new_size = None
    # brute force protection and identifier, replaces nonce
    #  16 = usercomponent.id in hexadecimal
    #  +1 for seperator
    token = models.CharField(
        max_length=(MAX_TOKEN_B64_SIZE)+hex_size_of_bigid+2,
        db_index=True, unique=True, null=True, blank=True,
        validators=[validator_token]
    )
    # regex disables controlcars and disable special spaces
    # and allows some of special characters
    name = models.CharField(
        max_length=255, blank=True, default="",
        validators=[
            content_name_validator
        ]
    )
    description = models.TextField(
        default="", blank=True
    )
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="contents", null=False, blank=False
    )
    features = models.ManyToManyField(
        "spider_base.ContentVariant",
        related_name="feature_for_contents", blank=True,
        limit_choices_to=models.Q(
            ctype__contains=VariantType.content_feature.value
        )
    )
    # ctype is here extended: VariantObject with abilities, name, model_name
    ctype = models.ForeignKey(
        ContentVariant, editable=False, null=True,
        on_delete=models.SET_NULL
    )
    priority = models.SmallIntegerField(default=0, blank=True)

    # creator = models.ForeignKey(
    #    settings.AUTH_USER_MODEL, editable=False, null=True,
    #    on_delete=models.SET_NULL
    # )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # only editable for admins
    deletion_requested = models.DateTimeField(
        null=True, blank=True, default=None
    )
    # required protection strength (real)
    strength = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(10)],
        editable=False
    )
    # required protection strength for links, 11 to disable links
    strength_link = models.PositiveSmallIntegerField(
        default=0, validators=[validators.MaxValueValidator(11)],
        editable=False
    )
    attached_to_primary_anchor = models.BooleanField(
        default=False, editable=False, null=False,
        help_text=_(
            "Content references primary anchor"
        )
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, editable=False
    )
    object_id = models.BigIntegerField(editable=False)
    content = GenericForeignKey(
        'content_type', 'object_id', for_concrete_model=False
    )
    # for quick retrieval!! even maybe a duplicate
    # layouts referencing models are not appearing here, so do it here
    references = models.ManyToManyField(
        "self", related_name="referenced_by", editable=False,
        symmetrical=False
    )
    # info extra flags:
    #  primary: primary content of type for usercomponent
    #  unlisted: not listed
    objects = UserContentManager()

    class Meta:
        unique_together = [
            ('content_type', 'object_id'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['usercomponent', 'info'], name='unique_info'
            ),
            # models.UniqueConstraint(
            #     fields=['usercomponent', 'name'], name='unique_name',
            #     condition=~models.Q(name='')
            # )
        ]

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<AssignedContent: ({}: {})>".format(
            self.usercomponent.username,
            self.name
        )

    def get_absolute_url(self, scope="view"):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"token": self.token, "access": scope}
        )

    # use next_object, last_object instead get_next_by_FOO, ...
    # for preventing disclosure of elements

    def get_size(self):
        if not self.content:
            return 0
        return self.content.get_size()

    def localized_description(self):
        """ """
        if not self.content:
            return self.description
        return self.content.localized_description()

    def clean(self):
        _ = gettext
        if VariantType.persist.value in self.ctype.ctype:
            if not self.attached_to_token:
                raise ValidationError(
                    _('Persistent token required'),
                    code="persist",
                )

        if not self.usercomponent.user_info.allowed_content.filter(
            name=self.ctype.name
        ).exists():
            raise ValidationError(
                message=_('Not an allowed ContentVariant for this user'),
                code='disallowed_contentvariant'
            )
        if self.strength > self.usercomponent.strength:
            raise ValidationError(
                _('Protection strength too low, required: %(strength)s'),
                code="strength",
                params={'strength': self.strength},
            )
        super().clean()
