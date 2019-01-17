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
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.hashers import (
    check_password, make_password
)
from django.utils.translation import gettext_lazy as _

from ..contents import BaseContent, add_content
from ..constants.static import (
    TravelLoginType, VariantType
)

logger = logging.getLogger(__name__)


@add_content
class PersistenceFeature(BaseContent):
    appearances = [
        {
            "name": "Persistence",
            "ctype": VariantType.feature.value,
            "strength": 0
        },
    ]

    class Meta:
        abstract = True

    @classmethod
    def action_urls(cls):
        return [
            (reverse("spider_base:token-delete-request"), "delete-request")
        ]


@add_content
class LinkContent(BaseContent):
    appearances = [{
        "name": "Link",
        "ctype": VariantType.raw_update.value
    }]

    content = models.ForeignKey(
        "spider_base.AssignedContent", related_name="+",
        on_delete=models.CASCADE
    )

    push = models.BooleanField(
        blank=True, default=False,
        help_text=_("Push Link to top.")
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

    def get_priority(self):
        priority = self.content.content.get_priority()
        # pin to top
        if self.pin and priority < 1:
            return 1
        return priority

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

    def serialize(self, graph, content_ref, context):
        return self.content.content.serialize(
            graph, content_ref, context
        )

    def get_references(self):
        if not self.content:
            return []
        return [self.content]

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


login_choices = [
    (TravelLoginType.none.value, _("No Login protection")),

    (TravelLoginType.fake_login.value, _("Fake login")),
    # TODO: to prevent circumventing deletion_period, tie to modified
    (TravelLoginType.wipe.value, _("Wipe")),
    (TravelLoginType.wipe_user.value, _("Wipe User")),
]


_login_protection = _(
    "No Login Protection: normal, default<br/>"
    "Fake Login: fake login and index<br/>"
    "Wipe: Wipe protected content, "
    "except they are protected by a deletion period<br/>"
    "Wipe User: destroy user on login"
)


class TravelProtectionManager(models.Manager):
    def get_active(self, now=None, no_stop=False):
        if not now:
            now = timezone.now()
        q = models.Q(active=True, start__lte=now)
        if not no_stop:
            q &= (models.Q(stop__isnull=True) | models.Q(stop__gte=now))
        return self.get_queryset().filter(q)


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
            # "ctype": VariantType.unique.value
        }
    ]

    objects = TravelProtectionManager()

    active = models.BooleanField(default=False)
    is_fake = models.BooleanField(default=False)
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
        blank=True
    )

    def check_password(self, raw_password):
        """
        Return a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """
        def setter(raw_password):
            self.hashed_secret = make_password(raw_password)
            self.save(update_fields=["hashed_secret"])
        return check_password(
            raw_password, self.hashed_secret, setter
        )

    def get_strength_link(self):
        return 5

    def get_priority(self):
        # pin to top with higher priority
        return 2

    def get_form(self, scope):
        from ..forms import TravelProtectionForm
        return TravelProtectionForm

    def get_info(self):
        ret = super().get_info()
        return ret

    def get_form_kwargs(self, **kwargs):
        ret = super().get_form_kwargs(**kwargs)
        ret["uc"] = kwargs["uc"]
        ret["request"] = kwargs["request"]
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
        if self.hashed_secret:
            if not self.check_password(
                kwargs["request"].GET.get("travel", "")
            ):
                return "failure"
        self.active = False
        self.save()
        return "success"

    def render(self, **kwargs):
        if kwargs["scope"] == "deactivate":
            return self.render_deactivate()
        return super().render(**kwargs)
