__all__ = ["CreateEntry"]

from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .models import DataVerificationTag
from .constants import get_hashob


_source_url_help = _("""
    Url to content or content list to verify
""")

_source_file_help = _("""
    File with data to verify
""")


class CreateEntry(forms.ModelForm):

    class Meta:
        model = DataVerificationTag
        fields = ["source", "dvfile"]
        widgets = {
            "source": widgets.URLInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].help_text = _source_url_help
        if getattr(settings, "VERIFIER_ALLOW_FILE_UPLOAD", False):
            self.fields["dvfile"].help_text = _source_file_help
        else:
            self.fields["dvfile"].disabled = True
            self.fields["dvfile"].widget = widgets.HiddenInput()

    def clean(self):
        ret = super().clean()
        if not ret["dvfile"]:

            h = get_hashob()
            with ret["dvfile"].open("rb") as fi:
                for chunk in fi.chunks():
                    h.update(chunk)
            ret["hash"] = h.hexdigest()
        return ret
