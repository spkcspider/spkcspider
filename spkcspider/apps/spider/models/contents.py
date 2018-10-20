"""
Basic Contents like TravelProtection, or Links
namespace: spider_base

"""

__all__ = [
    "LinkContent", "TravelProtection"
]

import logging
from datetime import timedelta

from django.db import models
from django.shortcuts import redirect
from django.utils.translation import gettext
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..contents import BaseContent, add_content
from ..constants.static import (
    TravelLoginType, UserContentType
)

logger = logging.getLogger(__name__)


@add_content
class LinkContent(BaseContent):
    appearances = [{
        "name": "Link",
        "ctype": UserContentType.raw_update.value
    }]

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
        return self.content.content.get_strength()

    def get_strength_link(self):
        # don't allow links linking on links
        return 11

    def get_protected_preview(self):
        return self.content.content.get_protected_preview()

    def get_info(self):
        ret = self.content.content.get_info()
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

    def render(self, **kwargs):
        if kwargs["scope"] == "add":
            return self.render_add(**kwargs)
        elif kwargs["scope"] == "update":
            return self.render_update(**kwargs)
        elif kwargs["scope"] == "raw_update":
            return redirect(
                'spider_base:ucontent-access',
                id=self.content.id,
                nonce=self.content.nonce,
                access='update'
            )
        elif kwargs["scope"] == "export":
            return self.render_serialize(**kwargs)

        kwargs["source"] = self
        kwargs["uc"] = self.content.usercomponent
        return self.content.content.render(**kwargs)


def own_components():
    return models.Q(
        user=models.F("associated_rel__usercomponent__user"),
        strength__lt=10  # don't disclose other index
    ) & ~models.Q(
        travel_protected__in=TravelProtection.objects.get_active()
    ) & ~models.Q(
        public=True  # this would easily expose the travel mode
    )


login_choices = [
    (TravelLoginType.none.value, _("No Login protection")),
]
if getattr(settings, "DANGEROUS_TRAVEL_PROTECTIONS", False):
    login_choices += [
        (TravelLoginType.fake_login.value, _("Fake login")),
        # TODO: to prevent circumventing deletion_period, tie to modified
        (TravelLoginType.wipe.value, _("Wipe")),
        (TravelLoginType.wipe_user.value, _("Wipe User")),
    ]

_login_protection = _("""
    No Login Protection: normal, default
    Fake Login: fake login and index (experimental)
    Wipe: Wipe protected content,
    except they are protected by a deletion period
    Wipe User: destroy user on login


    <div>
        Danger: every option other than: "No Login Protection" can screw you.
        "Fake Login" can trap you in a parallel reality
    </div>
""")


class TravelProtectionManager(models.Manager):
    def get_active(self):
        now = timezone.now()
        return self.get_queryset().filter(
            models.Q(active=True, start__lte=now) &
            (models.Q(stop__isnull=True) | models.Q(stop__gte=now))
        )


def default_start():
    return timezone.now()+timedelta(hours=3)


def default_stop():
    return timezone.now()+timedelta(days=7)


@add_content
class TravelProtection(BaseContent):
    appearances = [
        {
            "name": "TravelProtection",
            "strength": 10,
            # "ctype": UserContentType.unique.value
        }
    ]

    objects = TravelProtectionManager()

    active = models.BooleanField(default=False)
    start = models.DateTimeField(default=default_start, null=False)
    # no stop for no termination
    stop = models.DateTimeField(default=default_stop, null=True)

    login_protection = models.CharField(
        max_length=10, choices=login_choices,
        default=TravelLoginType.none.value, help_text=_login_protection
    )
    # use defaults from user
    hashed_secret = models.CharField(
        null=True, max_length=128
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

    def get_info(self):
        ret = super().get_info()
        return ret

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

    def render_deactivate(self, **kwargs):
        self.active = False
        self.save()
        return "success"

    def render(self, **kwargs):
        if kwargs["scope"] == "deactivate":
            return self.render_deactivate()
        return super().render(**kwargs)
