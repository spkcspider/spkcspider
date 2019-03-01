__all__ = ["ContractSource", "Contract", "Transaction"]

from decimal import Decimal
from datetime import timedelta
import logging

from django.db import settings
from django.utils.functional import cached_property
from django.db import models
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.core.validators import MinValueValidator
from django.utils.translation import gettext
from django.utils import timezone
# , gettext_lazy as _

from django.core.exceptions import ValidationError


import requests
import certifi


from spkcspider.apps.spider.constants.static import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.models import AssignedContent
# , ContentVariant


@add_content
class ContractSource(BaseContent):
    """ for payments and contracts """
    # should be encrypted
    secret = models.TextField(null=False)
    provider = models.ForeignKey(
        "spider_base.ReferrerObject"
    )
    description = models.TextField(
        default="", blank=True
    )
    _tmp_features = ()

    appearances = [
        {
            "name": "ContractSource",
            "strength": 5
        }
    ]


@add_content
class Contract(BaseContent):
    """ total=0 => Contract """
    token = models.ForeignKey(
        "spider_base.AuthToken", blank=True, null=True,
        on_delete=models.SET_ZERO, related_name="payments"
    )

    # for periodic payments
    period = models.DurationField(
        null=True, blank=True,
        validators=[MinValueValidator(timedelta(days=1))]
    )
    description = models.TextField(
        default="", blank=True
    )

    #: Currency code
    currency = models.CharField(max_length=10)
    #: Total amount (gross)
    total = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal('0.0')
    )

    appearances = [
        {
            "name": "SpiderPay",
            "ctype": (
                VariantType.feature.value
            ),
            "strength": 5
        }
    ]

    @classmethod
    def feature_urls(cls):
        return [
            ActionUrl(reverse("spider_base.payments-list"), "payments-list")
        ]

    def get_size(self):
        return 0

    def get_priority(self):
        # low priority
        return -10

    def clean(self):
        _ = gettext
        if self.kwargs:
            # return (decimal, str) or (None, None)
            self.total, self.currency = get_settings_func(
                "SPIDER_PAYMENT_VALIDATOR",
                "spkcspider.apps.spider.functions.clean_payment_default"
            )(
                self.kwargs["request"].GET.get("amount", None),
                self.kwargs["request"].GET.get("cur", "")
            )
            if self.total is None or self.currency is None:
                raise ValidationError(
                    _('Invalid payment parameters'),
                    code="invalid_payment_parameters",
                )
            if self.total != 0 and "period" in self.kwargs["request"].GET:
                try:
                    self.period = timedelta(
                        days=int(self.kwargs["request"].GET["period"])
                    )
                except ValueError:
                    raise ValidationError(
                        _('Invalid repeation period'),
                        code="invalid_period",
                    )
        super().clean()

    def access_capture(self, **kwargs):
        # TODO check that POST method is used
        source = ContractSource.objects.filter(
            provider=kwargs["request"].POST.get("provider", None)
        ).first()
        if not source:
            return HttpResponse(
                "invalid provider", status_code=400
            )

        if source.total == 0:
            return HttpResponse(
                "is contract", status_code=400
            )

        amount = kwargs["request"].POST.get("amount", "")
        try:
            if not amount:
                raise ValueError()
            amount = Decimal(amount)
        except ValueError:
            return HttpResponse(
                "invalid or not specified amount", status_code=400
            )

        if self.remaining < amount:
            return HttpResponse(
                "insufficient funds", status_code=400
            )

        associated = AssignedContent(
            usercomponent=self.assciated.usercomponent,
            ctype=VariantType.objects.get(
                name="SpiderPayTransaction"
            ),
        )
        associated.token_generate_new_size = \
            getattr(settings, "TOKEN_SIZE", 30)
        instance = Transaction.static_create(associated=associated)
        instance.payment = self
        # instance.

        instance.clean()
        instance.save()
        self.transaction

    def access_transactions(self):
        pass

    def get_info(self):
        ret = super().get_info()
        if not self.associated.info:
            return "{}url={}\n".format(
                ret, self.token.referrer.url.replace("\n", "%0A"),
            )
        else:
            # reuse old info url
            return "{}url={}\n".format(
                ret, self.associated.getlist("url", 1)[0]
            )

    @cached_property
    def remaining(self):
        if self.period is None:
            total = self.total
        else:
            total = (timezone.now()-self.associated.created)//self.period
            total *= self.total

        return total-self.transactions.aggregate(
            n=models.Sum('captured')
        ).get("n", 0)


@add_content
class Transaction(BaseContent):
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE, related_name="transactions"
    )
    source = models.ForeignKey(
        ContractSource,
        on_delete=models.CASCADE, related_name="transactions"
    )
    description = models.TextField(
        default="", blank=True
    )

    status_url = models.URLField(max_length=400, null=False)

    captured = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal('0.0')
    )

    appearances = [
        {
            "name": "PayTransaction",
            "ctype": (
                VariantType.unlisted + VariantType.domain_mode
            ),
            "strength": 0
        }
    ]

    def access_view(self, **kwargs):
        # redirects to confirmation url
        return HttpResponseRedirect(
            redirect_to=self.status_url
        )

    def access_cancel(self, **kwargs):
        # refund token is maybe required
        payload = kwargs["request"].GET.get("payload", None)
        try:
            d = {
                "secret": self.source.secret,
            }
            if payload:
                d["payload"] = payload

            ret = requests.post(
                self.status_url,
                data=d,
                verify=certifi.where()
            )
            ret.raise_for_status()
        except requests.exceptions.SSLError as exc:
            logging.info(
                "url: \"%s\" has a broken ssl configuration",
                self.status_url, exc_info=exc
            )
            return HttpResponse(
                "cancelation_failed", status_code=500
            )
        except Exception as exc:
            logging.info(
                "cancelation failed: \"%s\" failed",
                self.status_url, exc_info=exc
            )
            return HttpResponse(
                "cancelation_failed", status_code=500
            )
        HttpResponse(
            "success", status_code=200
        )
