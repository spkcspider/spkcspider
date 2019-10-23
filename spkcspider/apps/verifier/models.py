import datetime

import requests

from django.conf import settings
from django.core import exceptions
from django.db import models
from django.test import Client
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from spider_domainauth.abstract_models import BaseReverseToken
from spkcspider.constants.verifier import VERIFICATION_CHOICES

from .conf import get_requests_params
from .functions import get_anchor_domain


def dv_path(instance, filename):
    return 'dvfiles/{}/{}.{}'.format(
        datetime.datetime.now().strftime("%Y/%m"),
        instance.hash,
        "ttl"
    )


class VerifySourceObject(BaseReverseToken):
    id = models.BigAutoField(primary_key=True, editable=False)
    url = models.URLField(
        max_length=(
            400 if (
                settings.DATABASES["default"]["ENGINE"] !=
                "django.db.backends.mysql"
            ) else 255
        ), db_index=True, unique=True
    )
    get_params = models.TextField()

    def get_url(self, access=None):
        if access:
            split = self.url.rsplit("view", 1)
            if len(split) == 1:
                raise Exception()
            return "{}{}/?{}".format(split[0], access, self.get_params)
        return "{}?{}".format(self.url, self.get_params)


class DataVerificationTag(models.Model):
    """ Contains verified data """
    # warning: never depend directly on user, seperate for multi-db setups
    id = models.BigAutoField(primary_key=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    hash = models.SlugField(
        unique=True, db_index=True, null=False,
        max_length=255
    )
    dvfile = models.FileField(
        upload_to=dv_path, null=True, blank=True, help_text=_(
            "File with data to verify"
        )
    )
    source = models.ForeignKey(
        VerifySourceObject, null=True, blank=True, on_delete=models.CASCADE
    )
    # url = models.URLField(max_length=600)
    data_type = models.CharField(default="layout", max_length=20)
    checked = models.DateTimeField(null=True, blank=True)
    verification_state = models.CharField(
        default="pending",
        max_length=10, choices=VERIFICATION_CHOICES
    )
    note = models.TextField(default="", blank=True)

    class Meta:
        permissions = [("can_verify", "Can verify Data Tag?")]

    def __str__(self):
        return "DVTag: ...%s" % self.hash[:30]

    def get_absolute_url(self):
        return reverse(
            "spider_verifier:verify",
            kwargs={
                "hash": self.hash
            }
        )

    def callback(self, hostpart=None):
        if not hostpart:
            hostpart = get_anchor_domain()
        if self.source and self.data_type.endswith("_cb"):
            vurl = self.source.get_url("verify")
            body = {
                "url": "{}{}".format(
                    hostpart, self.get_absolute_url()
                )
            }
            params, inline_domain = get_requests_params(vurl)

            if inline_domain:
                resp = Client().post(
                    vurl, follow=True, secure=True, data=body,
                    Connection="close", SERVER_NAME=inline_domain
                )
                if resp.status_code != 200:
                    raise exceptions.ValidationError(
                        _("Retrieval failed: %(reason)s"),
                        params={"reason": resp.content},
                        code="error_code:{}".format(resp.status_code)
                    )
            else:
                try:
                    with requests.post(
                        vurl, data=body, headers={"Connection": "close"},
                        **params
                    ) as resp:
                        if resp.status_code != 200:
                            raise exceptions.ValidationError(
                                _("Retrieval failed: %(reason)s"),
                                params={"reason": resp.reason},
                                code="error_code:{}".format(resp.status_code)
                            )
                except requests.exceptions.Timeout:
                    raise exceptions.ValidationError(
                        _('url timed out: %(url)s'),
                        params={"url": vurl},
                        code="timeout_url"
                    )
                except requests.exceptions.ConnectionError:
                    raise exceptions.ValidationError(
                        _('invalid url: %(url)s'),
                        params={"url": vurl},
                        code="invalid_url"
                    )
