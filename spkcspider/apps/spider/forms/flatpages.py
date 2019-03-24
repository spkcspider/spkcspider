__all__ = ["FlatpageItemForm"]

import copy
from django.contrib.flatpages.forms import FlatpageForm
from django.utils.translation import gettext_lazy as _
from ..widgets import TrumbowygWidget

_help_text = _(
    """Example: '/about/contact/'. Make sure to have leading and trailing slashes.
    <br/>Special Urls (ordered by url):<br/>
    /home/heading/*/ : flatpages used for heading on frontpage <br/>
    /home/main/*/ : flatpages used for general information on frontpage <br/>
    /gfooter/*/ : flatpage links with general informations (links will be rendered on every page)
    """  # noqa: E501
)


class FlatpageItemForm(FlatpageForm):
    url = copy.copy(FlatpageForm.base_fields["url"])
    url.help_text = _help_text

    class Meta(FlatpageForm.Meta):
        widgets = {
            "content": TrumbowygWidget()
        }
