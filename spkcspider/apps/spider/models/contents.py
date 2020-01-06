"""
Basic Contents like TravelProtection, or Links
namespace: spider_base

"""

__all__ = [
    "LinkContent", "PersistenceFeature", "DomainMode", "DefaultActions",
    "TravelProtection"
]

import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext, pgettext

from spkcspider.constants import ActionUrl, VariantType
from spkcspider.utils.fields import add_by_field

from .. import registry
from ..abstract_models import BaseContent
from .content_extended import DataContent

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

    @classmethod
    def feature_urls(cls, name):
        return registry.feature_urls.default_actions.items()

    class Meta:
        abstract = True


@add_by_field(registry.contents, "_meta.model_name")
class LinkContent(DataContent):
    appearances = [{
        "name": "Link",
        "ctype": VariantType.raw_update
    }]
    expose_name = False
    expose_description = False

    class Meta:
        proxy = True

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
        if self.free_data.get("push") and priority < 1:
            return 1
        return priority

    def get_strength_link(self) -> int:
        # don't allow links linking on links
        return 11

    def get_info(self):
        ret = self.associated.attached_to_content.content.get_info()
        return "%ssource=%s\x1elink\x1e" % (
            ret, self.associated_id
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


@add_by_field(registry.contents, "_meta.model_name")
class TravelProtection(DataContent):
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

    force_token_size = 60
    expose_name = False
    expose_description = False

    _anonymous_deactivation = False
    _prepared_info = None

    class Meta:
        proxy = True
        permissions = [
            (
                "use_dangerous_travelprotections",
                "Can use dangerous TravelProtections"
            )
        ]

    @classmethod
    def localize_name(cls, name):
        _ = pgettext
        if name == "TravelProtection":
            return _("content name", "Travel-Protection")
        else:
            return _("content name", "Self-Protection")

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
        # TODO: cleanup this hack
        # information are directly saved in info, protect field against
        # rewrites
        if self._prepared_info is None:
            return self.associated.info
        return "{}{}".format(
            super().get_info(unlisted=True),
            self._prepared_info
        )

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)
        self._prepared_info = None
        return ret
