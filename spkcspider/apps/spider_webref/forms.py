__all__ = ["WebReferenceForm"]

from django import forms
from .models import WebReference


class WebReferenceForm(forms.ModelForm):
    creation_url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebReference
        fields = ['config']

    def __init__(self, *, scope=None, user=None, **kwargs):
        super().__init__(**kwargs)
