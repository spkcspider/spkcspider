from django.db import models
from django.utils.translation import pgettext_lazy
from django.conf import settings

from jsonfield import JSONField

from urllib.parse import urlsplit


from spkbspider.apps.spider.contents import BaseContent

# Create your models here.

class AbstractBroker(BaseContent):
    CHOICES = [
        ("oauth", "OAUTH"),
        ("jwt", "JWT")

    ]
    brokertype = models.SlugField(max_length=10, choices=CHOICES)
    brokerdata = JSONField(default={})
    url = models.URLField(max_length=300, default="")

    class Meta:
        abstract = True

    def __str__(self):
        return urlsplit(self.url).netloc

    #def get_absolute_url(self):
    #    return reverse("spiderbroker:bk-view", kwargs={"user": self.user.username, "id": self.id})

class Broker(AbstractBroker):
    pass
class IBroker(AbstractBroker):
    pass

class Tag(BaseContent):
    name = models.CharField(max_length=100)
    content = models.CharField(max_length=100)

    def __str__(self):
        return name
