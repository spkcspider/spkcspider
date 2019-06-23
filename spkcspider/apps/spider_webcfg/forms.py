__all__ = ["WebConfigForm"]

from django import forms
from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    creation_url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config', 'creation_url']
