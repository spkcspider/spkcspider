__all__ = ["WebConfigForm"]

from django import forms
from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    # url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config']  # , 'created', 'modified', 'url']
