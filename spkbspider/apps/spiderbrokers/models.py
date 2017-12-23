from django.db import models
from django.utils.translation import pgettext_lazy
from django.conf import settings
from urllib.parse import urlsplit


from jsonfield import JSONField


from spkbspider.apps.spider.contents import BaseContent, add_content

# Create your models here.


def broker_choices():
    return [
        ("oauth", "OAUTH"),
        ("jwt", "JWT")
    ]


@add_content
class Broker(BaseContent):
    brokertype = models.SlugField(max_length=10, choices=broker_choices)
    brokerdata = JSONField(default={})
    url = models.URLField(max_length=300, default="")

    def __str__(self):
        return urlsplit(self.url).netloc

    def render(self, **context):
        sendob = {
            "caller": context["request"].POST.get("caller"),
            "request": context["request"].POST.get("request")
        }
        # auth stuff
        # receive result object
        # TODO: implement me
        result = None
        return result
