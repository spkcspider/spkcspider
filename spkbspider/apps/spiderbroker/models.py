from django.db import models
from django.utils.translation import pgettext_lazy
from django.conf import settings

from jsonfield import JSONField
import swapper

from urllib.parse import urlsplit

# Create your models here.

class AbstractBroker(models.Model):
    id = models.BigAutoField(primary_key=True)
    CHOICES = [
        ("oauth", "OAUTH"),
        ("jwt", "JWT")

    ]
    brokertype = models.SlugField(max_length=10, choices=CHOICES, editable=False)
    brokerdata = JSONField(default={}, editable=False)
    url = models.URLField(max_length=300, default="", editable=False)
    # for extra information e.g. content of broker
    extra = JSONField(default={})
    user = models.ForeignKey(settings.AUTH_USER_MODEL, editable=False)
    protected_by = models.ForeignKey(swapper.get_model_name('spiderpk', 'UserComponent'), blank=True, null=True, default=None)

    class Meta:
        abstract = True
        unique_together = [("url", "user"),]
        indexes = [
            models.Index(fields=['user', 'url']),
        ]

    def __str__(self):
        return urlsplit(self.url).netloc

class Broker(AbstractBroker):
    class Meta:
        swappable = swapper.swappable_setting('spiderbroker', 'Broker')
