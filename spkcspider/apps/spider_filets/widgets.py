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
    allow_multiple_selected = False

    def __init__(self, licenses, **kwargs):
        self.licenses = licenses
        super().__init__(**kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """ add license_urls to attrs."""
        ret = super().build_attrs(base_attrs, extra_attrs)
        d = dict(map(lambda x: (x[0], x[1]["url"])))
        ret["license_urls"] = json.dumps(d)
        return ret
