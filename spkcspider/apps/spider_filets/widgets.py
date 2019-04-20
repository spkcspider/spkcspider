__all__ = [
    "LicenseChooserWidget"
]


import json

# from django.forms import widgets
from django.conf import settings
# from django.utils.translation import gettext_lazy as _

from spkcspider.apps.spider.widgets import OpenChoiceWidget


_extra = '' if settings.DEBUG else '.min'


class LicenseChooserWidget(OpenChoiceWidget):
    licenses = None

    def __init__(self, licenses, allow_multiple_selected=False, **kwargs):
        self.licenses = licenses
        super().__init__(
            allow_multiple_selected=allow_multiple_selected, **kwargs
        )

    def build_attrs(self, base_attrs, extra_attrs=None):
        """ add license_urls to attrs."""
        ret = super().build_attrs(base_attrs, extra_attrs)
        d = dict(map(lambda x: (x[0], x[1]["url"]), self.licenses.items()))
        ret["license_urls"] = json.dumps(d)
        # ret.setdefault("style", "color:black;")
        return ret
