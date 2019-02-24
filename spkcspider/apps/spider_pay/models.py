__all__ = ["Payment", "Transaction"]

from decimal import Decimal
from datetime import timedelta

from django.utils.functional import cached_property
from django.db import models
from django.urls import reverse
from django.http import HttpResponse
from django.core.validators import MinValueValidator
from django.utils.translation import gettext
from django.utils import timezone
# , gettext_lazy as _

from django.core.exceptions import ValidationError

from spkcspider.apps.spider.constants.static import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
from spkcspider.apps.spider.helpers import get_settings_func
# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_content
class PaymentSource(BaseContent):
    # should be encrypted
    secret = models.TextField(null=False)
    provider = models.URLField(max_length=400)
    description = models.TextField(
        default="", blank=True
    )

    appearances = [
        {
            "name": "PaymentSource",
            "strength": 5
        }
    ]


@add_content
class Payment(BaseContent):
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
            if "period" in self.kwargs["request"].GET:
                try:
                    self.period = timedelta(
                        days=int(self.kwargs["request"].GET["period"])
                    )
                except ValueError:
                    raise ValidationError(
                        _('Invalid repeation period'),
                        code="invalid_period",
                    )

            # return decimal, str or None
            self.total, self.currency = get_settings_func(
                "SPIDER_PAYMENT_VALIDATOR",
                "spkcspider.apps.spider.functions.clean_payment_default"
            )(
                self.request.GET.get("amount", None),
                self.request.GET.get("cur", "")
            )
            if self.total is None or self.currency is None:
                raise ValidationError(
                    _('Invalid payment parameters'),
                    code="invalid_payment_parameters",
                )
        super().clean()

    def access_capture(self):
        if self.remaining <= Decimal(0):
            return HttpResponse(
                "insufficient funds", status_code=400
            )

    def access_refund(self):
        pass

    def get_info(self):
        ret = super().get_info()
        if not self.associated.info:
            return "{}url={}\n".format(
                ret, self.token.referrer.replace("\n", "%0A"),
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
    payment = models.ForeignKey(
        "spider_base.SpiderPayment",
        on_delete=models.CASCADE, related_name="transactions"
    )
    source = models.ForeignKey(
        PaymentSource,
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
            "name": "SpiderPayTransaction",
            "ctype": (
                VariantType.unlisted + VariantType.domain_mode
            ),
            "strength": 0
        }
    ]

    def access_view(self, **kwargs):
        # redirects to confirmation url
        pass

    def access_cancel(self, **kwargs):
        # refund token is maybe required
        pass
