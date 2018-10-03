
from collections import OrderedDict

from django.db import models
from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError

from jsonfield import JSONField


from spkcspider.apps.spider.contents import (
    BaseContent, add_content, UserContentType
)
CACHE_FORMS = {}

# Create your models here.


class TagLayout(models.Model):
    name = models.SlugField(max_length=255, null=False)
    layout = JSONField(default=[])
    default_verifiers = JSONField(default=[], blank=True)
    usertag = models.OneToOneField(
        "spider_tags.UserTagLayout", on_delete=models.CASCADE,
        related_name="layout", null=True, blank=True
    )

    class Meta(object):
        unique_together = [
            ("name", "usertag")
        ]

    def clean(self):
        if TagLayout.objects.filter(usertag=None, name=self.name).exists():
            raise ValidationError(
                _("Layout exists already"),
                code="unique"
            )

    def get_form(self):
        from .forms import generate_form
        id = self.usertag.pk if self.usertag else None
        form = CACHE_FORMS.get((self.name, id))
        if not form:
            form = generate_form("LayoutForm", self.layout)
            CACHE_FORMS[self.name, id] = form
        return form

    def __repr__(self):
        return "<TagLayout: %s>" % self.name

    def __str__(self):
        return "<TagLayout: %s>" % self.name


@add_content
class UserTagLayout(BaseContent):
    appearances = [
        {
            "name": "TagLayout",
            "ctype": UserContentType.unique.value,
            "strength": 10
        }
    ]

    def get_strength_link(self):
        return 11

    def get_info(self):
        return "%slayout=%s\n" % (
            super().get_info(),
            self.layout.name
        )

    def get_form(self, scope):
        if scope == "add":
            from .forms import TagLayoutForm
            return TagLayoutForm
        else:
            ret = self.layout.get_form()
            if scope not in ["update", "raw_update"]:
                for i in ret.fields:
                    i.disabled = True
            return ret

    def render_add(self, **kwargs):
        if not hasattr(self, "layout"):
            self.layout = TagLayout(usertag=self)
        return super().render_add(**kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs["instance"] = self.layout
        return super().get_form_kwargs(**kwargs)


@add_content
class SpiderTag(BaseContent):
    appearances = [
        {
            "name": "SpiderTag",
            "strength": 0
        }
    ]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,

    )
    tagdata = JSONField(default={}, blank=True)
    verified_by = JSONField(default=[], blank=True)
    primary = models.BooleanField(default=False, blank=True)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        return "%s: %s (%s)" % (
            self.localize_name("Tag"),
            self.layout.name,
            self.id
        )

    def get_strength_link(self):
        return 0

    def get_form(self, scope):
        from .forms import SpiderTagForm
        if scope == "add":
            return SpiderTagForm
        else:
            return self.layout.get_form()

    def get_form_kwargs(self, instance=None, **kwargs):
        if kwargs["scope"] == "add":
            ret = super().get_form_kwargs(
                instance=instance,
                **kwargs
            )
            ret["user"] = self.associated.usercomponent.user
        else:
            ret = super().get_form_kwargs(
                instance=False,
                **kwargs
            )
            ret["initial"] = self.tagdata.copy()
            ret["uc"] = self.associated.usercomponent
            ret["usertag"] = self
        return ret

    def extract_form(
        self, context, datadic, zipf=None, level=1, prefix="", form=None
    ):
        if not form:
            form = self.get_form(context["scope"])(
                **self.get_form_kwargs(disable_data=True, **context)
            )
        if getattr(form, "layout_generating_form", False):
            _datadic = OrderedDict()
            context["_current_order"] = context.pop("current_order", None)
        else:
            _datadic = datadic
            if context.get("_current_order", None):
                context["current_order"] = context["_current_order"]
        super().extract_form(
            context, _datadic, zipf=zipf, level=level, prefix=prefix,
            form=form
        )
        if getattr(form, "layout_generating_form", False):
            datadic["primary"] = _datadic["primary"]
            order = context.get("_current_order", None)
            if order:
                _norder = {"tagdata": []}
                order[-1].append("primary")
                order[-1].append(_norder)
                datadic["tagdata"] = form.encode_data(
                    _datadic, order=_norder["tagdata"]
                )
            else:
                datadic["tagdata"] = form.encode_data(_datadic)

    def encode_verifiers(self):
        return "".join(
            map(
                lambda x: "verified_by={}\n".format(
                    x.replace("\n", "%0A")
                ),
                self.verified_by
            )
        )

    def get_info(self):
        return "{}{}tag={}\n".format(
            super().get_info(unique=self.primary),
            self.encode_verifiers(),
            self.layout.name
        )
