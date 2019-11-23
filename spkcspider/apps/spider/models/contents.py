"""
Basic Contents like TravelProtection, or Links
namespace: spider_base

"""

__all__ = [
    "LinkContent", "PersistenceFeature", "DomainMode", "DefaultActions",
    "TravelProtection"
]

import logging
from base64 import b64encode
from datetime import timedelta

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from django.conf import settings
from django.db import models
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext
from spkcspider.utils.fields import add_by_field
from spkcspider.constants import (
    ActionUrl, TravelLoginType, VariantType, dangerous_login_choices,
    travel_scrypt_params
)

from ..contents import BaseContent
from .. import registry

logger = logging.getLogger(__name__)

# raw and export: use references
link_abilities = frozenset(["add", "update", "update_raw", "raw", "export"])


@add_by_field(registry.contents, "_meta.model_name")
class PersistenceFeature(BaseContent):
    appearances = [
        {
            "name": "Persistence",
            "ctype": VariantType.component_feature,
            "strength": 0
        },
    ]

    class Meta:
        abstract = True

    @classmethod
    def feature_urls(cls, name):
        return [
            ActionUrl(
                "renew-token",
                reverse("spider_base:token-renew")
            ),
        ]


@add_by_field(registry.contents, "_meta.model_name")
class DomainMode(BaseContent):
    appearances = [
        {
            "name": "DomainMode",
            "ctype": (
                VariantType.component_feature + VariantType.content_feature +
                VariantType.no_export
            ),
            "valid_feature_for": "*",
            "strength": 0
        },
    ]

    class Meta:
        abstract = True

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        return _("content name", "Domain Mode")


@add_by_field(registry.contents, "_meta.model_name")
class DefaultActions(BaseContent):
    appearances = [
        {
            "name": "DefaultActions",
            "ctype": (
                VariantType.component_feature + VariantType.no_export +
                VariantType.unlisted
            ),
            "strength": 0
        },
    ]

    actions = {
        (
            "delete-token", "spider_base:token-delete-request"
        )
    }

    @classmethod
    def feature_urls(cls, name):
        return map(lambda x: ActionUrl(x.name, reverse(x.url)), cls.actions)

    class Meta:
        abstract = True


@add_by_field(registry.contents, "_meta.model_name")
class LinkContent(BaseContent):
    appearances = [{
        "name": "Link",
        "ctype": VariantType.raw_update
    }]
    expose_name = False
    expose_description = False

    push: bool = models.BooleanField(
        blank=True, default=False,
        help_text=_("Improve ranking of this Link.")
    )

    def get_abilities(self, context):
        ret = set()
        if self.associated.getflag("anchor"):
            ret.add("anchor")
        return ret

    def get_content_name(self):
        return self.associated.attached_to_content.content.get_content_name()

    def get_content_description(self):
        return (
            self.associated.
            attached_to_content.
            content.
            get_content_description()
        )

    def get_strength(self) -> int:
        return self.associated.attached_to_content.content.get_strength()

    def get_priority(self) -> int:
        priority = self.associated.attached_to_content.content.get_priority()
        # pin to top
        if self.push and priority < 1:
            return 1
        return priority

    def get_strength_link(self) -> int:
        # don't allow links linking on links
        return 11

    def get_info(self):
        ret = self.associated.attached_to_content.content.get_info()
        return "%ssource=%s\x1elink\x1e" % (
            ret, self.associated.pk
        )

    def get_form(self, scope):
        from ..forms import LinkForm
        if scope in link_abilities:
            return LinkForm
        # maybe not required
        return self.associated.attached_to_content.content.get_form(scope)

    def get_form_kwargs(self, **kwargs):
        if kwargs["scope"] in link_abilities:
            ret = super().get_form_kwargs(**kwargs)
            ret["uc"] = kwargs["uc"]
            ret["request"] = kwargs["request"]
        else:
            # maybe not required anymore
            ret = self.associated.attached_to_content.content.get_form_kwargs(
                **kwargs
            )
        return ret

    def access_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Create Content Link"))
        return super().access_add(**kwargs)

    def access_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Update Content Link"))
        return super().access_update(**kwargs)

    def access_raw_update(self, **kwargs):
        return redirect(
            'spider_base:ucontent-access',
            token=self.associated.attached_to_content.token,
            access='update'
        )

    def access(self, context):
        # context is updated and used outside!!
        if context["scope"] in link_abilities:
            return super().access(context)
        else:
            context["source"] = self
            context["uc"] = self.associated.attached_to_content.usercomponent
            ret = self.access(context)
            ret["uc"] = self.associated.usercomponent
            return ret


login_choices = [
    (TravelLoginType.hide, _("Hide")),
    (TravelLoginType.trigger_hide, _("Hide if triggered")),
    (TravelLoginType.disable, _("Disable login")),
    (TravelLoginType.trigger_disable, _("Disable login if triggered")),
    (TravelLoginType.wipe, _("Wipe")),
    (TravelLoginType.wipe_user, _("Wipe User")),
]

login_choices_dict = dict(login_choices)


class TravelProtectionManager(models.Manager):
    def get_active(self, now=None):
        if not now:
            now = timezone.now()
        q = models.Q(active=True)
        q &= (
            models.Q(start__isnull=True) | models.Q(start__lte=now)
        )
        q &= (models.Q(stop__isnull=True) | models.Q(stop__gte=now))

        q &= (
            models.Q(approved=True) |
            ~models.Q(login_protection__in=dangerous_login_choices)
        )
        return self.filter(q)

    def get_active_for_session(self, session, user, now=None):
        q = ~models.Q(associated_rel__info__contains="\x1epwhash=")
        if user.is_authenticated:
            for pw in session.get("travel_hashed_pws", []):
                q |= models.Q(
                    associated_rel__info__contains="\x1epwhash=%s\x1e" % pw
                )
            q &= models.Q(associated_rel__usercomponent__user=user)
        return self.get_active(now).filter(q)

    def get_active_for_request(self, request, now=None):
        return self.get_active_for_session(request.session, request.user)

    def auth(self, request, uc, now=None):
        active = self.get_active(now).filter(
            associated_rel__usercomponent=uc
        )

        request.session["travel_hashed_pws"] = list(map(
            lambda x: b64encode(Scrypt(
                salt=settings.SECRET_KEY.encode("utf-8"),
                backend=default_backend(),
                **travel_scrypt_params
            ).derive(x[:128].encode("utf-8"))).decode("ascii"),
            request.POST.getlist("password")[:4]
        ))

        q = ~models.Q(associated_rel__info__contains="\x1epwhash=")
        for pw in request.session["travel_hashed_pws"]:
            q |= models.Q(
                associated_rel__info__contains="\x1epwhash=%s\x1e" % pw
            )

        active = active.filter(q)

        request.session["is_travel_protected"] = active.exists()

        # use cached result instead querying
        if not request.session["is_travel_protected"]:
            return True

        for i in active:
            if TravelLoginType.disable == i.login_protection:
                return False
            elif TravelLoginType.trigger_hide == i.login_protection:
                i.login_protection = TravelLoginType.hide
                # don't re-add trigger passwords here
                if i.associated.getflag("anonymous_deactivation"):
                    i._encoded_form_info = \
                        "{}anonymous_deactivation\x1e".format(
                            i._encoded_form_info
                        )
                if i.associated.getflag("anonymous_trigger"):
                    i._encoded_form_info = \
                        "{}anonymous_trigger\x1e".format(
                            i._encoded_form_info
                        )
                i.clean()
                # assignedcontent is fully updated
                i.save(update_fields=["login_protection"])
            elif TravelLoginType.trigger_disable == i.login_protection:
                i.login_protection = TravelLoginType.disable
                # don't re-add trigger passwords here
                if i.associated.getflag("anonymous_deactivation"):
                    i._encoded_form_info = \
                        "{}anonymous_deactivation\x1e".format(
                            i._encoded_form_info
                        )
                if i.associated.getflag("anonymous_trigger"):
                    i._encoded_form_info = \
                        "{}anonymous_trigger\x1e".format(
                            i._encoded_form_info
                        )
                i.clean()
                # assignedcontent is fully updated
                i.save(update_fields=["login_protection"])
            elif TravelLoginType.wipe_user == i.login_protection:
                uc.user.delete()
                return False
            elif TravelLoginType.wipe == i.login_protection:
                # first components have to be deleted
                i.protect_components.all().delete()
                # as this deletes itself and therefor the information
                # about affected components
                i.protect_contents.all().delete()
        return True


@add_by_field(registry.contents, "_meta.model_name")
class TravelProtection(BaseContent):
    # should not be a feature as it would be detectable this way
    appearances = [
        {
            "name": "TravelProtection",
            "strength": 10,
        },
        {
            "name": "SelfProtection",
            "strength": 10,
        }
    ]

    objects = TravelProtectionManager()

    active = models.BooleanField(default=False, blank=True)
    # no start for always valid = self protection
    start = models.DateTimeField(blank=True, null=True)
    # no stop for no termination
    stop = models.DateTimeField(blank=True, null=True)
    approved = models.BooleanField(default=False, blank=True)

    login_protection = models.CharField(
        max_length=1, choices=login_choices,
        default=TravelLoginType.hide
    )

    protect_components = models.ManyToManyField(
        "spider_base.UserComponent", related_name="travel_protected",
        blank=True, limit_choices_to={
            "strength__lt": 10,
        }
    )
    protect_contents = models.ManyToManyField(
        "spider_base.AssignedContent", related_name="travel_protected",
        blank=True
    )

    force_token_size = 60
    expose_name = False
    expose_description = False

    _anonymous_deactivation = False
    _encoded_form_info = ""

    class Meta:
        default_permissions = ()
        permissions = [
            (
                "approve_travelprotection",
                "Can approve dangerous TravelProtections"
            )
        ]

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        if name == "TravelProtection":
            return _("content name", "Travel-Protection")
        else:
            return _("content name", "Self-Protection")

    def get_content_name(self):
        if self.start and self.stop:
            if self.stop - self.start < timedelta(days=1):
                return "{}:{}–{}".format(
                    login_choices_dict[self.login_protection],
                    self.start.time(),
                    self.stop.time()
                )
            return "{}:{}–{}".format(
                login_choices_dict[self.login_protection],
                self.start.date(),
                self.stop.date()
            )
        elif self.start:
            return "{}:{}–inf".format(
                login_choices_dict[self.login_protection],
                self.start.date()
            )
        else:
            return "{}: -".format(
                login_choices_dict[self.login_protection]
            )

        stop = self.stop or "-"
        return "{}:{}–{}".format(
            login_choices_dict[self.login_protection],
            self.start.date(),
            stop != "-" and stop.date()
        )

    def get_strength_link(self):
        return 11

    def get_priority(self):
        # pin to top with higher priority
        return 2

    def get_form(self, scope):
        from ..forms import TravelProtectionForm
        return TravelProtectionForm

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["request"] = kwargs["request"]
        return ret

    def access_add(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Create Travel Protection"))
        # redirect, so user does not see token, needs msg foo for sending token
        # token = self.associated.token
        ret = super().access_add(**kwargs)
        # if (
        #     token != self.associated.token and
        #     TravelProtection.objects.get_active().filter(pk=self.pk).exists()
        # ):
        #     return redirect(
        #         'spider_base:ucontent-list', kwargs={
        #            "token": kwargs.get("source", self.usercomponent).token
        #        }
        #    )
        return ret

    def access_update(self, **kwargs):
        _ = gettext
        kwargs["legend"] = escape(_("Update Travel Protection"))
        # redirect, so user does not see token, needs msg foo for sending token
        # token = self.associated.token
        ret = super().access_update(**kwargs)
        # if (
        #     token != self.associated.token and
        #     TravelProtection.objects.get_active().filter(pk=self.pk).exists()
        # ):
        #     return redirect(
        #         'spider_base:ucontent-list', kwargs={
        #             "token": kwargs.get("source", self.usercomponent).token
        #        }
        #    )
        return ret

    def get_info(self):
        return "{}{}".format(
            super().get_info(unlisted=True),
            self._encoded_form_info
        )
