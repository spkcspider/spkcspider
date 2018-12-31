__all__ = ["WebConfigForm"]

from django import forms
from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    # url = forms.URLField(disabled=True, required=False)

    class Meta:
        model = WebConfig
        fields = ['config', 'url', 'creation_url']

    def __init__(self, *, scope=None, user=None, **kwargs):
        super().__init__(**kwargs)
        self.fields["creation_url"].disabled = True
        if scope not in ("add", "update", "export"):
            del self.fields["url"]
            if scope is not None:
                del self.fields["config"]
        elif scope is not None and not user.is_superuser and not user.is_staff:
            self.fields["config"].disabled = True
