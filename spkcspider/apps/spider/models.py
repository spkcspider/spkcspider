"""
User Components, (Base)Contents and Protections
namespace: spider_base

"""

import logging
import datetime

from jsonfield import JSONField

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.views.decorators.debug import sensitive_variables

from .contents import installed_contents, BaseContent, add_content
from .protections import installed_protections

from .helpers import token_nonce, MAX_NONCE_SIZE
from .constants import ProtectionType, UserContentType, ProtectionResult

try:
    from captcha.fields import CaptchaField  # noqa: F401
    force_captcha = getattr(settings, "REQUIRE_LOGIN_CAPTCHA", False)
except ImportError:
    force_captcha = False

logger = logging.getLogger(__name__)


protected_names = ["index"]

hex_size_of_bigid = 16

default_uctoken_duration = getattr(
    settings, "DEFAULT_UCTOKEN_DURATION",
    datetime.timedelta(days=7)
)


def _get_default_amount():
    if models.F("name") == "index" and force_captcha:
        return 2
    elif models.F("name") == "index":
        return 1
    else:
        return 0  # protections are optional


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


class UserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3
    )
    public = models.BooleanField(
        default=False,
        help_text="Is public findable?"
    )
    required_passes = models.PositiveIntegerField(
        default=_get_default_amount,
        help_text=_required_passes_help
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False,
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    token_duration = models.DurationField(
        default=default_uctoken_duration,
        null=False
    )
    # only editable for admins
    deletion_requested = models.DateTimeField(null=True, default=None)
    contents = None
    # should be used for retrieving active protections, related_name
    protections = None

    class Meta:
        unique_together = [("user", "name")]
        indexes = [
            models.Index(fields=['user']),
        ]

    def __repr__(self):
        return "<UserComponent: %s: %s>" % (self.username, self.name)

    def __str__(self):
        return self.__repr__()

    def auth(self, request, ptype=ProtectionType.access_control.value,
             protection_codes=None, **kwargs):
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
    def name_protected(self):
        """ Is it allowed to change the name """
        return self.name in protected_names

    @property
    def no_public(self):
        """ Can the usercomponent be turned public """
        return self.name == "index" or self.contents.filter(
            info__contains="no_public;"
        )

    def save(self, *args, **kwargs):
        if self.name == "index" and self.public:
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
                raise SystemExit('A possible infinite loop was detected')
            self.create_auth_token()
            try:
                self.validate_unique()
                break
            except ValidationError:
                pass
        super().save(*args, **kwargs)


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


class UserContent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    # brute force protection
    nonce = models.SlugField(
        default=token_nonce, max_length=MAX_NONCE_SIZE*4//3
    )
    # fix linter warning
    objects = models.Manager()
    usercomponent = models.ForeignKey(
        UserComponent, on_delete=models.CASCADE,
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
        indexes = [
            models.Index(fields=['usercomponent']),
            models.Index(fields=['object_id']),
        ]

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


class ProtectionManager(models.Manager):
    def invalid(self):
        return self.get_queryset().exclude(code__in=installed_protections)

    def valid(self):
        return self.get_queryset().filter(code__in=installed_protections)


# don't confuse with Protection objects used with add_protection
# this is pure DB
class Protection(models.Model):
    objects = ProtectionManager()
    usercomponents = None
    # autogenerated, no choices required
    code = models.SlugField(max_length=10, primary_key=True)
    # protection abilities/requirements
    ptype = models.CharField(
        max_length=10, default=ProtectionType.authentication.value
    )

    @property
    def installed_class(self):
        return installed_protections[self.code]

    def __str__(self):
        return self.localize_name()

    def __repr__(self):
        return "<Protection: %s>" % self.__str__()

    def localize_name(self):
        if self.code not in installed_protections:
            return self.code
        return self.installed_class.localize_name(self.code)

    def auth_localize_name(self):
        if self.code not in installed_protections:
            return self.code
        return self.installed_class.auth_localize_name(self.code)

    @sensitive_variables("kwargs")
    def auth(self, request, obj=None, **kwargs):
        # never ever allow authentication if not active
        if obj and not obj.active:
            return False
        if self.code not in installed_protections:
            return False
        return self.installed_class.auth(
            obj=obj, request=request, **kwargs.copy()
        )

    @classmethod
    def auth_query(cls, request, query, required_passes=1, **kwargs):
        ret = []
        for item in query:
            obj = None
            _instant_fail = False
            if hasattr(item, "protection"):  # is AssignedProtection
                item, obj = item.protection, item
                _instant_fail = obj.instant_fail
            result = item.auth(
                request=request, obj=obj, query=query, **kwargs
            )
            if _instant_fail:  # instant_fail does not reduce required_passes
                if result is not True:  # False or form
                    # set limit unreachable
                    required_passes = len(query)
            elif result is True:
                required_passes -= 1
            if result is not False:  # False will be not rendered
                ret.append(ProtectionResult(result, item))
        # don't require lower limit this way and
        # against timing attacks
        if required_passes <= 0:
            return True
        return ret

    @classmethod
    def authall(cls, request, required_passes=1,
                ptype=ProtectionType.authentication.value,
                protection_codes=None, **kwargs):
        """
            Usage: e.g. prerendering for login fields, because
            no assigned object is available there is no config
        """
        query = cls.objects.filter(ptype__contains=ptype)

        # before protection_codes, for not allowing users
        # to manipulate required passes
        if required_passes > 0:
            # required_passes 1 and no protection means: login only
            required_passes = max(min(required_passes, len(query)), 1)

        if protection_codes:
            query = query.filter(
                code__in=protection_codes
            )
        if "reliable" in request.GET:
            query = query.filter(
                ptype__contains=ProtectionType.reliable.value
            )
        return cls.auth_query(
            request, query.order_by("code"), required_passes=required_passes,
            ptype=ptype
        )

    def get_form(self, prefix=None, **kwargs):
        if prefix:
            protection_prefix = "{}_protections_{{}}".format(prefix)
        else:
            protection_prefix = "protections_{}"
        return self.installed_class(
            protection=self, prefix=protection_prefix.format(self.code),
            **kwargs
        )

    @classmethod
    def get_forms(cls, ptype=None, **kwargs):
        protections = cls.objects.valid()
        if ptype:
            protections = protections.filter(ptype__contains=ptype)
        else:
            ptype = ""
        return map(lambda x: x.get_form(ptype=ptype, **kwargs), protections)


def get_limit_choices_assigned_protection():
    # django cannot serialize static, classmethods
    ret = \
        {
            "code__in": Protection.objects.valid(),
            "ptype__contains": ProtectionType.access_control.value
        }
    if models.F("usercomponent__name") == "index":
        ret["ptype__contains"] = ProtectionType.authentication.value
    return ret


class AssignedProtection(models.Model):
    id = models.BigAutoField(primary_key=True)
    # fix linter warning
    objects = models.Manager()
    protection = models.ForeignKey(
        Protection, on_delete=models.CASCADE, related_name="assigned",
        limit_choices_to=get_limit_choices_assigned_protection, editable=False
    )
    usercomponent = models.ForeignKey(
        UserComponent, related_name="protections",
        on_delete=models.CASCADE, editable=False
    )
    # data for protection
    data = JSONField(default={}, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    active = models.BooleanField(default=True)
    instant_fail = models.BooleanField(
        default=False,
        help_text=_("Auth fails if test fails, stronger than required_passes\n"
                    "Works even if required_passes=0\n"
                    "Does not contribute to required_passes, "
                    "ideal for side effects"
                    )
    )

    class Meta:
        unique_together = [("protection", "usercomponent")]
        indexes = [
            models.Index(fields=['usercomponent']),
        ]

    def __str__(self):
        return "%s -> %s" % (
            self.usercomponent, self.protection.localize_name()
        )

    def __repr__(self):
        return "<Assigned: %s>" % (
            self.__str__()
        )

    @classmethod
    def authall(cls, request, usercomponent,
                ptype=ProtectionType.access_control.value,
                protection_codes=None, **kwargs):
        query = cls.objects.filter(
            protection__ptype__contains=ptype, active=True,
            usercomponent=usercomponent
        )
        # before protection_codes, for not allowing users
        # to manipulate required passes
        if usercomponent.required_passes > 0:
            required_passes = max(
                min(
                    usercomponent.required_passes,
                    len(query.exclude(instant_fail=True))
                ), 1
            )
        elif usercomponent.name == "index":
            # enforce a minimum of required_passes, if index
            required_passes = 1
        else:
            required_passes = 0

        if protection_codes:
            query = query.filter(
                protection__code__in=protection_codes
            )

        if "reliable" in request.GET:
            query = query.filter(
                ptype__contains=ProtectionType.reliable.value
            )

        return Protection.auth_query(
            request, query.order_by("protection__code"),
            required_passes=required_passes, ptype=ptype
        )

    @property
    def user(self):
        return self.usercomponent.user

###############################################################################


@add_content
class LinkContent(BaseContent):
    # links are not linkable
    appearances = [("Link", UserContentType.public.value)]

    content = models.ForeignKey(
        "spider_base.UserContent", related_name="+",
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
