__all__ = ["WebConfigForm"]
# "AnchorGovForm"


from django import forms
from .models import WebConfig
# AnchorGov, ID_VERIFIERS


class WebConfigForm(forms.ModelForm):
    url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config', 'created', 'modified', 'url']
