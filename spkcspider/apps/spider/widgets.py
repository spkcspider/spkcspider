__all__ = [
    "OpenChoiceWidget", "StateButtonWidget", "HTMLWidget",
    "SubSectionStartWidget", "SubSectionStopWidget", "ListWidget"
]


from django.forms import widgets
from django.conf import settings
from django.utils.translation import get_language, gettext_lazy as _


_extra = '' if settings.DEBUG else '.min'


class StateButtonWidget(widgets.CheckboxInput):
    template_name = 'spider_base/forms/widgets/statebutton.html'
    # ugly as hell

    class Media:
        css = {
            'all': [
                'spider_base/statebutton.css'
            ]
        }


class ListWidget(widgets.SelectMultiple):
    template_name = 'spider_base/forms/widgets/wrapped_select.html'
    allow_multiple_selected = True

    class Media:
        js = [
            'node_modules/@json-editor/json-editor/dist/jsoneditor%s.js' % _extra,  # noqa:E501
            'spider_base/ListEditorWidget.js'
        ]

    def __init__(
        self, *, attrs=None, wrapper_attrs=None,
        format_type="text", item_label=_("item"), **kwargs
    ):
        if not attrs:
            attrs = {"class": ""}
        if not wrapper_attrs:
            wrapper_attrs = {}
        attrs.setdefault("class", "")
        attrs["class"] += " SpiderListTarget"
        attrs["format_type"] = format_type
        # don't access them as they are lazy evaluated
        attrs["item_label"] = item_label
        self.wrapper_attrs = wrapper_attrs.copy()
        super().__init__(attrs=attrs, **kwargs)

    def __deepcopy__(self, memo):
        obj = super().__deepcopy__(memo)
        obj.wrapper_attrs = self.wrapper_attrs.copy()
        return obj

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['wrapper_attrs'] = self.wrapper_attrs
        context['widget']['wrapper_attrs']["id"] = "{}_inner_wrapper".format(
            context['widget']['attrs']["id"]
        )
        return context

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []

        for index, option_value in enumerate(value or []):
            if option_value is None:
                option_value = ''
            # selected = True
            groups.append((
                None,
                [self.create_option(
                    name, option_value, option_value, True, index,
                    subindex=None, attrs=attrs,
                )],
                index
            ))
        return groups


class HTMLWidget(widgets.Input):
    template_name = 'spider_base/forms/widgets/info.html'
    input_type = "html_widget"

    def __init__(self, *, template_name=None, **kwargs):
        if template_name:
            self.template_name = template_name
        super().__init__(**kwargs)

    def use_required_attribute(self, initial):
        return False

    def format_value(self, value):
        return None

    def value_omitted_from_data(self, data, files, name):
        return None


class SubSectionStartWidget(HTMLWidget):
    input_type = "start_pseudo"
    template_name = 'spider_base/forms/widgets/subsectionstart.html'
    label = None

    def __init__(self, *, label=None, **kwargs):
        self.label = label
        super().__init__(**kwargs)

    def get_context(self, name, value, attrs):
        ret = super().get_context(name, value, attrs)
        ret["label"] = self.label
        return ret


class SubSectionStopWidget(HTMLWidget):
    input_type = "stop_pseudo"
    template_name = 'spider_base/forms/widgets/subsectionstop.html'


class Select2Widget(widgets.Select):
    class Media:
        js = [
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            'node_modules/select2/dist/js/select2%s.js' % _extra,
            'spider_base/Select2Widget.js'
        ]
        css = {
            'all': [
                'node_modules/select2/dist/css/select2%s.css' % _extra
            ]
        }

    def __init__(self, allow_multiple_selected, *, attrs=None, **kwargs):
        self.allow_multiple_selected = allow_multiple_selected
        if not attrs:
            attrs = {"class": ""}
        attrs.setdefault("class", "")
        attrs["class"] += " Select2WidgetTarget"
        super().__init__(attrs=attrs, **kwargs)


class OpenChoiceWidget(widgets.Select):
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

    def __init__(self, allow_multiple_selected, *, attrs=None, **kwargs):
        self.allow_multiple_selected = allow_multiple_selected
        if not attrs:
            attrs = {"class": ""}
        attrs.setdefault("class", "")
        attrs["class"] += " OpenChoiceTarget"
        super().__init__(attrs=attrs, **kwargs)

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        groups2 = []
        has_selected = False

        choices = list(self.choices)
        value_set = set(value)
        # optimization
        if isinstance(value, set):
            value = value_set

        lastindex = 0
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
                selected = False
                if str(subvalue) in value_set:
                    value_set.remove(str(subvalue))
                    selected = True
                selected = (
                    selected and
                    (not has_selected or self.allow_multiple_selected)
                )
                has_selected |= selected
                subgroup.append(self.create_option(
                    name, subvalue, sublabel, selected, index,
                    subindex=subindex, attrs=attrs,
                ))
                if subindex is not None:
                    subindex += 1
            lastindex = index

        for index, option_value in enumerate(value, lastindex):
            if option_value not in value_set:
                continue
            if option_value is None:
                option_value = ''

            subgroup = [self.create_option(
                name, option_value, option_value,
                (not has_selected or self.allow_multiple_selected), index,
                subindex=None, attrs=attrs,
            )]
            groups2.append((None, subgroup, index))

        return groups2 + groups


class TrumbowygWidget(widgets.Textarea):
    template_name = 'spider_base/forms/widgets/wrapped_textarea.html'

    _media = widgets.Media(
        css={
            'all': [
                'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                'node_modules/trumbowyg/dist/plugins/emoji/ui/trumbowyg.emoji.css',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
                # 'node_modules/jquery-resizable/resizable.css',
            ]
        },
        js=[
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
    )
    @property
    def media(self):
        if not self.is_localized:
            return self._media
        lang = get_language()
        if not lang or lang.startswith("en"):
            return self._media
        lang = lang.replace("-", "_")
        return widgets.Media(
            css={
                'all': [
                    'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                    'node_modules/trumbowyg/dist/plugins/emoji/ui/trumbowyg.emoji.css',  # noqa: E501
                    'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                    # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
                    # 'node_modules/jquery-resizable/resizable.css',
                ]
            },
            js=[
                'node_modules/jquery/dist/jquery%s.js' % _extra,
                # 'node_modules/jquery-resizable/resizable.js',
                'node_modules/trumbowyg/dist/trumbowyg%s.js' % _extra,
                'node_modules/trumbowyg/dist/plugins/emoji/trumbowyg.emoji.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/preformatted/trumbowyg.preformatted.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/insertaudio/trumbowyg.insertaudio.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/lineheight/trumbowyg.lineheight.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
                # 'node_modules/trumbowyg/dist/plugins/resizimg/trumbowyg.resizimg.js',  # noqa: E501
                'node_modules/trumbowyg/dist/plugins/table/trumbowyg.table.min.js',  # noqa: E501
                'spider_base/trumbowygWidget.js',
                'node_modules/trumbowyg/dist/langs/{}.min.js'.format(
                    lang
                )
            ]
        )

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
