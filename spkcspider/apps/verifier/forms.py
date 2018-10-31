__all__ = ["CreateEntryForm"]


from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile

import requests
from rdflib import Graph

from spkcspider.apps.spider.helpers import merge_get_url

from .models import DataVerificationTag
from .constants import get_hashob, BUFFER_SIZE


_source_url_help = _("""
    Url to content or content list to verify
""")

_source_file_help = _("""
    File with data to verify
""")


def hash_entry(triple):
    h = get_hashob()
    h.update(triple[0].encode("ascii"))
    h.update(triple[1].encode("ascii"))
    h.update(triple[2].datatype.encode("ascii"))
    h.update(triple[2].value.encode("ascii"))
    return h.digest()


class CreateEntryForm(forms.ModelForm):
    url = forms.URLField(help_text=_source_url_help)

    class Meta:
        model = DataVerificationTag
        fields = ["dvfile", "hash"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hash"].required = False
        self.fields["hash"].disabled = True
        self.fields["hash"].widget = widgets.HiddenInput()
        if getattr(settings, "VERIFIER_ALLOW_FILE_UPLOAD", False):
            self.fields["dvfile"].help_text = _source_file_help
            self.fields["url"].required = False
        else:
            self.fields["dvfile"].disabled = True
            self.fields["dvfile"].widget = widgets.HiddenInput()

    def clean(self):
        ret = super().clean()
        if not ret.get("url", None) and not ret.get("dvfile", None):
            raise forms.ValidationError(
                _('Require either url or dvfile'),
                code="missing_parameter"
            )
        elif not ret["dvfile"]:
            url = self.cleaned_data["url"]
            url = merge_get_url(url, raw="embed")
            if not settings.DEBUG and not url.startswith("https://"):
                self.add_error(
                    "url", forms.ValidationError(
                        _('Insecure url scheme'),
                        code="insecure_scheme"
                    )
                )
                return
            try:
                resp = requests.get(url, stream=True)
            except requests.exceptions.ConnectionError:
                self.add_error(
                    "url", forms.ValidationError(
                        _("invalid url"),
                        code="invalid_url"
                    )
                )
                return
            if resp.status_code != 200:
                self.add_error(
                    "url", forms.ValidationError(
                        _("Retrieval failed: %s") % resp.reason,
                        code=str(resp.status_code)
                    )
                )
                return

            if (
                "content-length" not in resp.headers or
                not resp.headers["content-length"].isdigit()
            ):
                self.add_error(
                    "url", forms.ValidationError(
                        _("Retrieval failed, no length specified or invalid"),
                        code="invalid_length"
                    )
                )
                return
            # TODO:verify length
            self.cleaned_data["dvfile"] = TemporaryUploadedFile(
                "url_uploaded", resp.headers.get(
                    'content-type', "application/octet-stream"
                ),
                int(resp.headers["content-length"]),
                "ascii"
            )
            dvfile = self.cleaned_data["dvfile"].open("wb")
            for chunk in resp.iter_content(BUFFER_SIZE):
                dvfile.write(chunk)

        g = Graph()
        g.parse(
            self.cleaned_data["dvfile"].temporary_file_path(), format="turtle"
        )

        hashes = [
            hash_entry(i) for i in g.triples((None, None, None))
        ]
        hashes.sort()

        h = get_hashob()
        for i in hashes:
            h.update(i)
        self.cleaned_data["hash"] = h.hexdigest()
        self.fields["hash"].initial = ret["hash"]
        self.fields["dvfile"].initial = ret["dvfile"]
        return self.cleaned_data
