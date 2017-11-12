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
    brokertype = models.SlugField(max_length=10, choices=CHOICES)
    brokerdata = JSONField(default={})
    url = models.URLField(max_length=300, default="")
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    # for extra information e.g. content of broker, admin only editing
    content_info = models.TextField(null=False, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, editable=False)
    protected_by = models.ForeignKey(swapper.get_model_name('spiderucs', 'UserComponent'), blank=True, null=True, default=None, related_name="brokers")

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
