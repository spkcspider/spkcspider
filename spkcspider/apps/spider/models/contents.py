"""
(Base)Contents
namespace: spider_base

"""

__all__ = [
    "ContentVariant", "AssignedContent", "LinkContent",
    "TravelProtection"
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
from django.utils import timezone

from ..user import UserComponent
from ..contents import installed_contents, BaseContent, add_content
from ..protections import installed_protections

# from ..constants import UserContentType
from ..helpers import token_nonce, MAX_NONCE_SIZE

logger = logging.getLogger(__name__)


# ContentType is already occupied
class ContentVariant(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # usercontent abilities/requirements
    ctype = models.CharField(
        max_length=10, default=""
    )
    code = models.CharField(max_length=255)
    name = models.SlugField(max_length=50, unique=True)
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
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3
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

    def get_flag(self, flag):
        if self.info and "\n%s\n" % flag in self.info:
            return True
        return False

    def getlist(self, key):
        info = self.info
        ret = []
        pstart = info.find("\n%s=" % key)
        while pstart != -1:
            pend = info.find("\n", pstart+len(key)+1)
            if pend == -1:
                raise Exception(
                    "Info field error: doesn't end with \"\\n\": \"%s\"" %
                    info
                )
            ret.append(info[pstart:pend])
            pstart = info.find("\n%s=" % key, pend)
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

###############################################################################


@add_content
class LinkContent(BaseContent):
    appearances = [{"name": "Link"}]

    content = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE
    )

    def __str__(self):
        if getattr(self, "content", None):
            return "Link: <%s>" % self.content
        else:
            return "Link"

    def __repr__(self):
        if getattr(self, "content", None):
            return "<Link: %r>" % self.content
        else:
            return "<Link>"

    def get_strength(self):
        return self.content.get_strength()

    def get_strength_link(self):
        # don't allow links linking on links
        return 11

    def get_info(self):
        ret = super().get_info()
        return "%ssource=%s\nlink\n" % (
            ret, self.associated.pk
        )

    def get_form(self, scope):
        from ..forms import LinkForm
        if scope in ["add", "update", "export", "raw"]:
            return LinkForm
        return self.content.content.get_form(scope)

    def get_form_kwargs(self, **kwargs):
        if kwargs["scope"] in ["add", "update", "export", "raw"]:
            ret = super().get_form_kwargs(**kwargs)
            ret["uc"] = kwargs["uc"]
        else:
            ret = self.content.content.get_form_kwargs(**kwargs)
        return ret

    def render_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Create Content Link")
        return super().render_add(**kwargs)

    def render_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Update Content Link")
        return super().render_update(**kwargs)

    def render_view(self, **kwargs):
        kwargs["source"] = self
        kwargs["uc"] = self.content.usercomponent
        return self.content.content.render(**kwargs)


# TODO: should enforce self-protection (own component is on protected list)


def own_components():
    return models.Q(
        user=models.F("associated_rel__usercomponent__user")
    )


@add_content
class TravelProtection(BaseContent):
    appearances = [
        {
            "name": "TravelProtection",
            "strength": 10,
            # "ctype": UserContentType.unique.value
        }
    ]

    active = models.BooleanField(default=False)
    # null for fake TravelProtection
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False,
        related_name="travel_protection", null=True
    )

    disallow = models.ManyToManyField(
        "spider_base.UserComponent", related_name="travel_protected",
        limit_choices_to=own_components
    )

    def get_strength_link(self):
        return 5

    def get_form(self, scope):
        from ..forms import TravelProtectionForm
        return TravelProtectionForm

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["uc"] = kwargs["uc"]
        user = self.associated.usercomponent.user
        travel_protection = getattr(user, "travel_protection", None)
        if (
            travel_protection and not travel_protection.is_active and
            user == kwargs["request"].user
        ):
            ret["travel_protection"] = travel_protection
        return ret

    def render_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Create Travel Protection")
        return super().render_add(**kwargs)

    def render_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = _("Update Travel Protection")
        return super().render_update(**kwargs)

    def render_view(self, **kwargs):
        return ""

    @property
    def is_active(self):
        if not self.active:
            return False
        now = timezone.now()
        if self.block_times.filter(
            start__le=now,
            stop__ge=now
        ).exists():
            return True
        return self.active


class TravelProtectionTime(models.Model):
    travel_protection = models.ForeignKey(
        TravelProtection, on_delete=models.CASCADE, related_name="block_times"
    )
    start = models.DateTimeField()
    stop = models.DateTimeField()
