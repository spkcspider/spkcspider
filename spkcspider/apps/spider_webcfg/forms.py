__all__ = ["WebConfigForm"]

from django import forms
from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    creation_url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config']
        widgets = {
            "config": forms.Textarea()
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.initial["creation_url"] = \
            self.instance.associated.attached_to_token.referrer.url
