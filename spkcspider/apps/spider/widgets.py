__all__ = ["OpenChoiceWidget", "StateButtonWidget", "InfoWidget"]


from django.forms import widgets
from django.conf import settings


_extra = '' if settings.DEBUG else '.min'


class StateButtonWidget(widgets.CheckboxInput):
    template_name = 'spider_base/forms/widgets/statebutton.html'

    class Media:
        css = {
            'all': [
                'spider_base/statebutton.css'
            ]
        }


class InfoWidget(widgets.Input):
    template_name = 'spider_base/forms/widgets/info.html'
    input_type = "info_widget"


class Select2Multiple(widgets.SelectMultiple):
    class Media:
        css = {
            'all': [
                'node_modules/select2/dist/css/select2.min.css'
            ]
        }
        js = [
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            'node_modules/select2/dist/js/select2%s.js' % _extra,
            'spider_base/Select2MultipleWidget.js'
        ]

    def __init__(self, *, attrs=None, **kwargs):
        if not attrs:
            attrs = {"class": ""}
        attrs.setdefault("class", "")
        attrs["class"] += " Select2MultipleTarget"
        super().__init__(attrs=attrs, **kwargs)


class TrumbowygWidget(widgets.Textarea):
    template_name = 'spider_base/forms/widgets/trumbowygwidget.html'

    class Media:
        css = {
            'all': [
                'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                'node_modules/trumbowyg/dist/plugins/emoji/ui/trumbowyg.emoji.css',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
                # 'node_modules/jquery-resizable/resizable.css',
            ]
        }
        js = [
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            # 'node_modules/jquery-resizable/resizable.js',
            'node_modules/trumbowyg/dist/trumbowyg%s.js' % _extra,
            'node_modules/trumbowyg/dist/plugins/emoji/trumbowyg.emoji.min.js',
            'node_modules/trumbowyg/dist/plugins/preformatted/trumbowyg.preformatted.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/insertaudio/trumbowyg.insertaudio.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/lineheight/trumbowyg.lineheight.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
            # 'node_modules/trumbowyg/dist/plugins/resizimg/trumbowyg.resizimg.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/table/trumbowyg.table.min.js',
            'spider_base/trumbowygWidget.js',
        ]

    def __init__(self, *, attrs=None, wrapper_attrs=None, **kwargs):
        if not attrs:
            attrs = {"class": ""}
        if not wrapper_attrs:
            wrapper_attrs = {"class": ""}
        attrs.setdefault("class", "")
        wrapper_attrs.setdefault("class", "")
        attrs["class"] += " TrumbowygTarget"
        wrapper_attrs["class"] += " TrumbowygTargetWrapper"
        self.wrapper_attrs = wrapper_attrs.copy()
        super().__init__(attrs=attrs, **kwargs)

    def __deepcopy__(self, memo):
        obj = super().__deepcopy__(memo)
        obj.wrapper_attrs = self.wrapper_attrs.copy()
        return obj

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['wrapper_attrs'] = self.wrapper_attrs
        return context


class OpenChoiceWidget(widgets.SelectMultiple):
    class Media:
        css = {
            'all': [
                'node_modules/select2/dist/css/select2.min.css'
            ]
        }
        js = [
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            'node_modules/select2/dist/js/select2%s.js' % _extra,
            'spider_base/OpenChoiceWidget.js'
        ]

    def __init__(self, *, attrs=None, **kwargs):
        if not attrs:
            attrs = {"class": ""}
        attrs.setdefault("class", "")
        attrs["class"] += " OpenChoiceTarget"
        super().__init__(attrs=attrs, **kwargs)

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        choices = list(self.choices)
        if value:
            choices = [(i, i) for i in value] + choices

        for index, (option_value, option_label) in enumerate(choices):
            if option_value is None:
                option_value = ''

            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = option_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(option_value, option_label)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel in choices:
                selected = (
                    str(subvalue) in value and
                    (not has_selected or self.allow_multiple_selected)
                )
                has_selected |= selected
                subgroup.append(self.create_option(
                    name, subvalue, sublabel, selected, index,
                    subindex=subindex, attrs=attrs,
                ))
                if subindex is not None:
                    subindex += 1
        return groups
