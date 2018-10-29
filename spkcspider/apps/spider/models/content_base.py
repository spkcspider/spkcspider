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

# from ..constants import UserContentType
from ..helpers import token_nonce
from ..constants.static import MAX_NONCE_SIZE

logger = logging.getLogger(__name__)


# ContentType is already occupied
class ContentVariant(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # usercontent abilities/requirements
    ctype = models.CharField(
        max_length=10, default=""
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

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<ContentVariant: %s>" % self.__str__()


def info_field_validator(value):
    _ = gettext
    prefixed_value = "\n%s" % value
    if value[-1] != "\n":
        raise ValidationError(
            _('%(value)s ends not with "\\n"'),
            code="syntax",
            params={'value': value},
        )
    if value[0] != "\n":
        raise ValidationError(
            _('%(value)s starts not with "\\n"'),
            code="syntax",
            params={'value': value},
        )
    # check elements
    for elem in value[:-1].split("\n"):
        f = elem.find("=")
        # no flag => allow multiple instances
        if f != -1:
            continue
        counts = 0
        counts += prefixed_value.count("\n%s\n" % elem)
        # check: is flag used as key in key, value storage
        counts += prefixed_value.count("\n%s=" % elem)
        assert(counts > 0)
        if counts > 1:
            raise ValidationError(
                _('flag not unique: %(element)s in %(value)s'),
                params={'element': elem, 'value': value},
            )


class AssignedContent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    fake_id = models.BigIntegerField(editable=False, null=True)
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3,
        db_index=False
    )
    # fix linter warning
    objects = models.Manager()
    usercomponent = models.ForeignKey(
        "spider_base.UserComponent", on_delete=models.CASCADE,
        related_name="contents", null=False, blank=False
    )
    # ctype is here extended: VariantObject with abilities, name, model_name
    ctype = models.ForeignKey(
        ContentVariant, editable=False, null=True,
        on_delete=models.SET_NULL
    )

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
    # for extra information over content, admin only editing
    # format: \nflag1\nflag2\nfoo=true\nfoo2=xd\n...\nendfoo=xy\n
    # every section must start and end with \n every keyword must be unique and
    # in this format: keyword=
    # no unneccessary spaces!
    # flags:
    #  primary: primary content of type for usercomponent
    info = models.TextField(
        null=False, editable=False,
        validators=[info_field_validator]
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

    def get_flag(self, flag):
        if self.info and "\n%s\n" % flag in self.info:
            return True
        return False

    def getlist(self, key, amount=None):
        info = self.info
        ret = []
        pstart = info.find("\n%s=" % key)
        while pstart != -1:
            tmpstart = pstart+len(key)+2
            pend = info.find("\n", tmpstart)
            if pend == -1:
                raise Exception(
                    "Info field error: doesn't end with \"\\n\": \"%s\"" %
                    info
                )
            ret.append(info[tmpstart:pend])
            pstart = info.find("\n%s=" % key, pend)
            # if amount=0 => bool(amount) == false
            if amount and amount <= len(ret):
                break
        return ret

    def clean(self):
        _ = gettext
        if not self.usercomponent.user_info.allowed_content.filter(
            name=self.ctype.name
        ).exists():
            raise ValidationError(
                _(
                    'Not an allowed ContentVariant for this user'
                )
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
                    message=_("Unique Content already exists."),
                    code='unique_together',
                )

    def get_absolute_url(self, scope="view"):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"id": self.id, "nonce": self.nonce, "access": scope}
        )
