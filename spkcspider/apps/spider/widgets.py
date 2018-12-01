__all__ = ["OpenChoiceWidget", "InfoWidget"]


from django.forms import widgets
from django.conf import settings


_extra = '' if settings.DEBUG else '.min'


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
            'spider_base/Select2Init.js'
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
