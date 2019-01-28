"""
Base for Contents
namespace: spider_base

"""

__all__ = [
    "ContentVariant", "AssignedContent"
]

import logging

from django.db import models
from django.utils.translation import gettext
from django.urls import reverse
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core import validators

from ..contents import installed_contents
from ..protections import installed_protections

# from ..constants import VariantType
from ..helpers import validator_token, create_b64_id_token
from ..constants.static import (
    MAX_TOKEN_B64_SIZE, VariantType, hex_size_of_bigid
)

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
    fake_id = models.BigIntegerField(editable=False, null=True)
    persist_token = models.ForeignKey(
        "spider_base.AuthToken", blank=True, null=True,
        limit_choices_to={"persist__gte": 0}, on_delete=models.CASCADE
    )
    # brute force protection
    nonce = models.SlugField(
        null=True, max_length=MAX_TOKEN_B64_SIZE,
        db_index=False, blank=True
    )
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
    objects = UserContentManager()
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="contents", null=False, blank=False
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
        "spider_base.AssignedContent", related_name="referenced_by",
        editable=False
    )
    # info extra flags:
    #  primary: primary content of type for usercomponent
    #  unlisted:

    class Meta:
        unique_together = [
            ('content_type', 'object_id'),
        ]
        if not getattr(settings, "MYSQL_HACK", False):
            unique_together.append(('usercomponent', 'info'))

    def __str__(self):
        return self.content.__str__()

    def __repr__(self):
        return self.content.__repr__()

    def get_id(self):
        """
            provides "right" id
            only neccessary for access from usercomponent to hide fakes
        """
        # access from content works out of the box by using associated
        if self.fake_id:
            return self.fake_id
        return self.id

    def get_size(self):
        if not self.content:
            return 0
        return self.content.get_size()

    def clean(self):
        _ = gettext
        if VariantType.persist.value in self.ctype.ctype:
            if not self.persist_token:
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

        if getattr(settings, "MYSQL_HACK", False):
            obj = AssignedContent.objects.filter(
                usercomponent=self.usercomponent,
                info=self.info
            ).first()

            if obj and obj.id != getattr(self, "id", None):
                raise ValidationError(
                    message=_("Unique Content already exists"),
                    code='unique_together',
                )

    def get_absolute_url(self, scope="view"):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"token": self.token, "access": scope}
        )
