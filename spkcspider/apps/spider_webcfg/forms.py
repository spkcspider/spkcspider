__all__ = ["WebConfigForm"]

from django import forms
from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    creation_url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config']

    def __init__(self, *, scope=None, user=None, **kwargs):
        super().__init__(**kwargs)
        self.fields["creation_url"].initial = self.instance.creation_url
