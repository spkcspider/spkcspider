__all__ = ["FlatpageItemForm"]

import copy
from django.contrib.flatpages.forms import FlatpageForm
from django.utils.translation import gettext_lazy as _

_help_text = _("""
    Example: '/about/contact/'. Make sure to have leading and trailing slashes.
    "<br/>Special Urls (ordered by url):<br/>
    /home/heading/*/ : flatpages used for heading on frontpage <br/>
    /home/main/*/ : flatpages used for general information on frontpage"
""")


class FlatpageItemForm(FlatpageForm):
    url = copy.copy(FlatpageForm.base_fields["url"])
    url.help_text = _help_text

    class Media:
        css = {
            'all': [
                'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                'spider_base/trumbowyg.css',
                # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
            ]
        }
        js = [
            'admin/js/vendor/jquery/jquery.min.js',
            'node_modules/trumbowyg/dist/trumbowyg.min.js',
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
            'spider_base/flatpage_admin.js',
        ]
