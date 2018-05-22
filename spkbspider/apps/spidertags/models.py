from django.db import models
from urllib.parse import urlsplit


from jsonfield import JSONField


from spkbspider.apps.spider.contents import BaseContent, add_content

# Create your models here.


class TagType(models.Model):
    layout = JSONField(default=[])
    default_verifiers = JSONField(default=[])



@add_content
class SpiderTag(BaseContent):
    tagtype = models.ForeignKey(TagType)
    tagdata = JSONField(default={})
    verfied_by = JSONField(default={})

    def __str__(self):
        return urlsplit(self.url).netloc
