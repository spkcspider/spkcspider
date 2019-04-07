__all__ = ["SchemeWidget"]

import json

from django.forms import widgets
from django.conf import settings


_extra = '' if settings.DEBUG else '.min'


class SchemeWidget(widgets.Textarea):
    template_name = 'spider_base/forms/widgets/wrapped_textarea.html'

    class Media:
        js = [
            'node_modules/jquery/dist/jquery%s.js' % _extra,
            'node_modules/select2/dist/js/select2%s.js' % _extra,
            'node_modules/@json-editor/json-editor/dist/jsoneditor%s.js' % _extra,  # noqa:E501,
            'spider_tags/scheme_editor.js'
        ]
        css = {
            'all': [
                'node_modules/select2/dist/css/select2%s.css' % _extra
            ]
        }

    def __init__(self, *, attrs=None, wrapper_attrs=None, **kwargs):
        if not attrs:
            attrs = {"class": ""}
        if not wrapper_attrs:
            wrapper_attrs = {}
        attrs.setdefault("class", "")
        attrs["class"] += " SchemeEditorTarget"
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

    def format_value(self, value):
        if not value:
            return "[]"
        if isinstance(value, (tuple, list)):
            value = json.dumps(value)
        return str(value)

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = ""
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, indent=2)

        return super().render(name, value, attrs, renderer)
