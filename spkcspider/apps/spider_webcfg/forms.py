__all__ = ["WebConfigForm"]

from django import forms
from spkcspider.apps.spider.forms.base import DataContentForm


class WebConfigForm(DataContentForm):
    creation_url = forms.URLField(disabled=True, required=False)
    config = forms.CharField(
        widget=forms.Textarea()
    )

    free_fields = {"creation_url": None}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        b = None
        if self.object.id:
            b = self.object.associated.attachedblobs.filter(
                name="config"
            ).first()
        if b:
            self.initial["config"] = b.blob.as_bytes.decode("ascii")
