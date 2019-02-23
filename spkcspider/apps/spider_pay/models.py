__all__ = ["Payment", "Transaction"]

from decimal import Decimal

from django.db import models


from spkcspider.apps.spider.constants import (
    MAX_TOKEN_B64_SIZE, hex_size_of_bigid
)
from spkcspider.apps.spider.helpers import validator_token
from spkcspider.apps.spider.constants.static import VariantType, ActionUrl
from spkcspider.apps.spider.contents import BaseContent, add_content
# from spkcspider.apps.spider.models.base import BaseInfoModel


@add_content
class Payment(BaseContent):
    token = models.ForeignKey(
        "spider_base.AuthToken", blank=True, null=True,
        on_delete=models.SET_ZERO, related_name="payments"
    )

    # for periodic payments
    period = models.DurationField(
        null=True, blank=True
    )

    appearances = [
        {
            "name": "SpiderPay",
            "ctype": (
                VariantType.feature.value
            ),
            "strength": 0
        }
    ]

    #: Currency code
    currency = models.CharField(max_length=10)
    #: Total amount (gross)
    total = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal('0.0')
    )

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


@add_content
class Transaction(BaseContent):
    payment = models.ForeignKey(
        "spider_base.SpiderPayment",
        on_delete=models.CASCADE
    )

    captured = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal('0.0')
    )
    provider = models.URLField(
        max_length=400, blank=True, null=True
    )

    appearances = [
        {
            "name": "SpiderPayTransaction",
            "ctype": (
                VariantType.unlisted.value
            ),
            "strength": 0
        }
    ]
