from django.db import models
from importlib import import_module

from django import forms

from jsonfield import JSONField


from spkcspider.apps.spider.contents import BaseContent, add_content

# Create your models here.


def order_fields(base, layout):
    ret = []
    for i in layout:
        split = list(i.items())[0]
        if isinstance(split[1], list):
            ret.append(order_fields(
                base.get(split[0], {}), split[1]
            ))
        else:
            ret.append(base.get(split[0]))
    return ret


def generate_fields(layout, base=None, prefix=""):
    ret = []
    for i in layout:
        split = list(i.items())[0]
        if isinstance(split[1], list):
            ret + generate_fields(
                split[1], prefix="%s_%s" % (prefix, split[0]),
                base=base.get(split[0], {}) if base else None
            )
        elif isinstance(split[1], dict):
            d = split[1].copy()
            field = getattr(forms, d.pop("field"))
            ret.append(field(initial=base.get(split[0]), **d))
        else:
            field = getattr(forms, split[1])
            ret.append(field(initial=base.get(split[0])))
    return ret


class TagType(models.Model):
    layout = JSONField(default=[])
    default_verifiers = JSONField(default=[])


@add_content
class SpiderTag(BaseContent):
    tagtype = models.ForeignKey(
        TagType, related_name="tags", on_delete=models.PROTECT
    )
    tagdata = JSONField(default={})
    verfied_by = JSONField(default=[])

    def get_ordered(self):
        return order_fields(self.tagdata, self.tagtype.layout)
