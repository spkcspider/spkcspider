__all__ = ["WebConfigForm"]

from django import forms

from .models import WebConfig


class WebConfigForm(forms.ModelForm):
    creation_url = forms.URLField(disabled=True, required=False)
    config = forms.CharField(
        widget=forms.Textarea()
    )

    class Meta:
        model = WebConfig

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        b = None
        if self.object.id:
            b = self.object.associated.blobs.filter(name="config").first()
        if b:
            self.initial["config"] = b.blob
        self.initial["creation_url"] = \
            self.instance.associated.attached_to_token.referrer.url
