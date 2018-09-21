__all__ = ["FlatpageItemForm"]


from django.contrib.flatpages.forms import FlatpageForm
from django.utils.translation import gettext_lazy as _


class FlatpageItemForm(FlatpageForm):
    url = FlatpageForm.base_fields["url"]
    url.help_text = _(
        url.help_text +
        "<br/>Special Urls: /home/main/*"
        # /home/sideleft/*, /home/sideright/*
    )

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
