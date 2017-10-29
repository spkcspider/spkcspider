from django.db import models
from django.utils.translation import pgettext_lazy
from django.conf import settings

from jsonfield import JSONField


from urllib.parse import urlsplit

# Create your models here.



class Broker(models.Model):
    id = models.BigAutoField(primary_key=True)
    CHOICES = [
        ("oauth", "OAUTH"),
        ("jwt", "JWT")

    ]
    brokertype = models.CharField(max_length=10, choices=CHOICES)
    brokerdata = JSONField(default={})
    url = models.URLField(max_length=300, default="")
    # for extra information e.g. content of broker
    extra = JSONField(default={})
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    class Meta:
        unique_together = [("url", "user"),]
        indexes = [
            models.Index(fields=['user', 'url']),
        ]


    def __str__(self):
        return urlsplit(self.url).netloc
