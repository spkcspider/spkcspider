from django.db import models
from django.utils.translation import pgettext_lazy
from django.contrib.contenttypes.fields import GenericRelation
from django.conf import settings

from jsonfield import JSONField
import swapper

from urllib.parse import urlsplit


from spkbspider.apps.spider.models import UserComponentContent

# Create your models here.

class AbstractBroker(models.Model):
    id = models.BigAutoField(primary_key=True)
    CHOICES = [
        ("oauth", "OAUTH"),
        ("jwt", "JWT")

    ]
    brokertype = models.SlugField(max_length=10, choices=CHOICES)
    brokerdata = JSONField(default={})
    url = models.URLField(max_length=300, default="")
    associated = GenericRelation(UserComponentContent)

    class Meta:
        abstract = True
        unique_together = [("url", "user"),]
        indexes = [
            models.Index(fields=['user', 'url']),
        ]

    def __str__(self):
        return urlsplit(self.url).netloc

    def get_absolute_url(self):
        return reverse("spiderbroker:bk-view", kwargs={"user": self.user.username, "id": self.id})

class Broker(AbstractBroker):
    class Meta:
        swappable = swapper.swappable_setting('spiderbrokers', 'Broker')
