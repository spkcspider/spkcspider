__all__ = [
    "LicenseChooserWidget"
]


import json

from django.forms import widgets
from django.conf import settings
# from django.utils.translation import gettext_lazy as _


_extra = '' if settings.DEBUG else '.min'


class LicenseChooserWidget(widgets.Select):
    licenses = None

    def __init__(self, licenses, **kwargs):
        self.licenses = licenses
        super().__init__(**kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Build an attribute dictionary."""
        ret = super().build_attrs(base_attrs, extra_attrs)
        d = dict(map(lambda x: (x[0], str(x[1][1])), self.licenses.items()))
        ret["licenses"] = json.dumps(d)
        return ret
