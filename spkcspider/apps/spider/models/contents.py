"""
(Base)Contents
namespace: spider_base

"""

__all__ = ["UserContentVariant", "AssignedContent", "LinkContent"]

import logging

from django.db import models
from django.utils.translation import gettext
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from ..contents import installed_contents, BaseContent, add_content
from ..protections import installed_protections

from ..helpers import token_nonce, MAX_NONCE_SIZE
from ..constants import UserContentType

logger = logging.getLogger(__name__)


class UserContentVariant(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # usercontent abilities/requirements
    ctype = models.CharField(
        max_length=10
    )
    code = models.CharField(max_length=255)
    name = models.SlugField(max_length=255, unique=True)

    @property
    def installed_class(self):
        return installed_contents[self.code]

    def localize_name(self):
        if self.code not in installed_protections:
            return self.code
        return self.installed_class.localize_name(self.code)

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<ContentVariant: %s>" % self.__str__()


def info_field_validator(value):
    _ = gettext
    prefixed_value = ";%s" % value
    if value[-1] != ";":
        raise ValidationError(
            _('%(value)s ends not with ;'),
            params={'value': value},
        )
    if value[0] != ";":
        raise ValidationError(
            _('%(value)s starts not with ;'),
            params={'value': value},
        )
    # check elements
    for elem in value[:-1].split(";"):
        f = elem.find("=")
        # flag
        if f != -1:
            elem = elem[:f]
        counts = 0
        counts += prefixed_value.count(";%s;" % elem)
        counts += prefixed_value.count(";%s=" % elem)
        assert(counts > 0)
        if counts > 1:
            raise ValidationError(
                _('multiple elements: %(element)s in %(value)s'),
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
        UserContentVariant, editable=False, null=True,
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
    # format: ;flag1;flag2;foo=true;foo2=xd;...;endfoo=xy;
    # every section must start and end with ; every keyword must be unique and
    # in this format: keyword=
    # no unneccessary spaces!
    # flags:
    #  no_public: cannot switch usercomponent public
    #  primary: primary content of type for usercomponent
    info = models.TextField(
        null=False, editable=False,
        validators=[info_field_validator]
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
            ('usercomponent', 'info'),
        ]
        # indexes = [
        #     models.Index(fields=['usercomponent']),
        #     models.Index(fields=['object_id']),
        # ]

    def __str__(self):
        return self.content.__str__()

    def __repr__(self):
        return self.content.__repr__()

    def get_flag(self, flag):
        if self.info and ";%s;" % flag in self.info:
            return True
        return False

    def get_value(self, key):
        info = self.info
        pstart = info.find(";%s=" % key)
        if pstart == -1:
            return None
        pend = info.find(";", pstart+len(key)+1)
        if pend == -1:
            raise Exception("Info field error: doesn't end with \";\": \"%s\""
                            % info)
        return info[pstart:pend]

    def clean(self):
        _ = gettext
        if UserContentType.confidential.value in self.ctype.ctype and \
           self.usercomponent.name != "index":
            raise ValidationError(
                _('Confidential usercontent is only allowed for index')
            )
        if UserContentType.public.value not in self.ctype.ctype and \
           self.usercomponent.public:
            raise ValidationError(
                _(
                    'Non-Public usercontent is only allowed for ' +
                    'usercomponents with "public = False"'
                )
            )

    def get_absolute_url(self):
        return reverse(
            "spider_base:ucontent-access",
            kwargs={"id": self.id, "nonce": self.nonce, "access": "view"}
        )

###############################################################################


@add_content
class LinkContent(BaseContent):
    # links are not linkable
    appearances = [("Link", UserContentType.public.value)]

    content = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE
    )

    def __str__(self):
        return "Link: <%s>" % self.content

    def __repr__(self):
        return "<Link: %r>" % self.content

    def get_info(self, usercomponent):
        ret = super().get_info(usercomponent)
        return "%ssource=%s;link;" % (
            ret, self.associated.pk
        )

    def render(self, **kwargs):
        from .forms import LinkForm
        _ = gettext
        if kwargs["scope"] in ["update", "add"]:
            if self.id:
                kwargs["legend"] = _("Update Content Link")
                kwargs["confirm"] = _("Update")
            else:
                kwargs["legend"] = _("Create Content Link")
                kwargs["confirm"] = _("Create")
            kwargs["form"] = LinkForm(
                uc=self.associated.usercomponent,
                **self.get_form_kwargs(kwargs["request"])
            )
            if kwargs["form"].is_valid():
                kwargs["form"] = LinkForm(
                    uc=self.associated.usercomponent,
                    instance=kwargs["form"].save()
                )
            template_name = "spider_base/base_form.html"
            return render_to_string(
                template_name, request=kwargs["request"],
                context=kwargs
            )
        else:
            kwargs["source"] = self
            return self.content.content.render(**kwargs)
