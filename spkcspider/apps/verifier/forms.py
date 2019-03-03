__all__ = ["CreateEntryForm"]

import tempfile
import shutil

from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _
from django.conf import settings

import requests
import certifi


from spkcspider.apps.spider.helpers import merge_get_url, get_settings_func
from .models import VerifySourceObject
from .validate import verify_download_size

_source_url_help = _(
    "Url to content or content list to verify"
)

_source_file_help = _(
    "File with data to verify"
)


class CreateEntryForm(forms.ModelForm):
    url = forms.URLField(help_text=_source_url_help)
    dvfile = forms.FileField(
        required=False, max_length=settings.VERIFIER_MAX_SIZE_DIRECT_ACCEPTED
    )
    # MAX_FILE_SIZE = forms.CharField(
    #    disabled=True, widget=forms.HiddenInput(), required=False,
    #    initial=settings.VERIFIER_MAX_SIZE_ACCEPTED
    # )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.VERIFIER_MAX_SIZE_DIRECT_ACCEPTED > 0:
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
            return ret
        if ret.get("url", None):
            self.cleaned_data["url"] = merge_get_url(
                self.cleaned_data["url"], raw="embed"
            )
            url = self.cleaned_data["url"]
            if not get_settings_func(
                "SPIDER_URL_VALIDATOR",
                "spkcspider.apps.spider.functions.validate_url_default"
            )(url):
                self.add_error(
                    "url", forms.ValidationError(
                        _('Insecure url: %(url)s'),
                        params={"url": url},
                        code="insecure_url"
                    )
                )
                return ret
            try:
                resp = requests.get(url, stream=True, verify=certifi.where())
            except requests.exceptions.ConnectionError:
                self.add_error(
                    "url", forms.ValidationError(
                        _('invalid url: %(url)s'),
                        params={"url": url},
                        code="invalid_url"
                    )
                )
            if resp.status_code != 200:
                self.add_error(
                    "url", forms.ValidationError(
                        _("Retrieval failed: %s") % resp.reason,
                        code=str(resp.status_code)
                    )
                )

            if not verify_download_size(
                resp.headers.get("content-length", None), 0
            ):
                return
        return ret

    def save(self):
        if self.cleaned_data.get("url", None):
            split = self.cleaned_data["url"].split("?", 1)
            return VerifySourceObject.objects.update_or_create(
                url=split[0], defaults={"get_params": split[1]}
            )[0].id
        else:
            f = tempfile.mkstemp()
            shutil.copyfileobj(self.cleaned_data["dvfile"].file, f)
            return f.name, self.cleaned_data["dvfile"].size
