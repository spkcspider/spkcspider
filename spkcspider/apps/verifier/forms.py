__all__ = ["CreateEntryForm"]

from itertools import chain
import logging
import base64

from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import XSD

from spkcspider.apps.spider.helpers import merge_get_url
from spkcspider.apps.spider.constants.static import namespaces_spkcspider
from spkcspider.apps.spider.helpers import get_settings_func

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
    if triple[2].datatype == XSD.base64Binary:
        h.update(triple[2].datatype.encode("utf8"))
        h.update(triple[2].toPython())
    else:
        if triple[2].datatype:
            h.update(triple[2].datatype.encode("utf8"))
        h.update(triple[2].value.encode("utf8"))
    return h.digest()


class CreateEntryForm(forms.ModelForm):
    url = forms.URLField(help_text=_source_url_help)
    MAX_FILE_SIZE = forms.CharField(
        disabled=True, widget=forms.HiddenInput(), required=False,
        initial=settings.VERIFIER_MAX_SIZE_ACCEPTED
    )

    class Meta:
        model = DataVerificationTag
        fields = ["dvfile", "hash", "linked_hashes", "data_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hash"].required = False
        self.fields["hash"].disabled = True
        self.fields["hash"].widget = widgets.HiddenInput()
        self.fields["linked_hashes"].required = False
        self.fields["linked_hashes"].disabled = True
        self.fields["linked_hashes"].widget = widgets.HiddenInput()
        self.fields["data_type"].required = False
        self.fields["data_type"].disabled = True
        self.fields["data_type"].widget = widgets.HiddenInput()
        if getattr(settings, "VERIFIER_ALLOW_FILE_UPLOAD", False):
            self.fields["dvfile"].help_text = _source_file_help
            self.fields["url"].required = False
        else:
            self.fields["dvfile"].disabled = True
            self.fields["dvfile"].widget = widgets.HiddenInput()

    def _verify_download_size(length):
        if not length or not length.isdigit():
            return False
        length = int(length)
        if settings.VERIFIER_MAX_SIZE_ACCEPTED < length:
            return False
        return True

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
                        _('Insecure url scheme: %(url)s'),
                        params={"url": url},
                        code="insecure_scheme"
                    )
                )
                return
            try:
                resp = requests.get(url, stream=True)
            except requests.exceptions.ConnectionError:
                self.add_error(
                    "url", forms.ValidationError(
                        _('invalid url: %(url)s'),
                        params={"url": url},
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

            if not self._verify_download_size(
                resp.headers.get("content-length", None)
            ):
                self.add_error(
                    "url", forms.ValidationError(
                        _(
                            "Retrieval failed, no length specified, invalid\n"
                            "or too long, length: %(length)s"
                        ),
                        params={"length": resp.headers.get(
                            "content-length", None
                        )},
                        code="invalid_length"
                    )
                )
                return
            self.cleaned_data["dvfile"] = TemporaryUploadedFile(
                "url_uploaded", resp.headers.get(
                    'content-type', "application/octet-stream"
                ),
                int(resp.headers["content-length"]),
                "utf8"
            )
            self._dvfile_scope = self.cleaned_data["dvfile"].open("wb")
            for chunk in resp.iter_content(BUFFER_SIZE):
                self._dvfile_scope.write(chunk)
            self._dvfile_scope.seek(0, 0)

        g = Graph()
        try:
            g.parse(
                self.cleaned_data["dvfile"].temporary_file_path(),
                format="turtle"
            )
        except Exception as exc:
            with open(self.cleaned_data["dvfile"].temporary_file_path()) as f:
                logging.error(f.read())
            logging.exception(exc)
            raise forms.ValidationError(
                _("not a \"%(format)s\" file"),
                params={"format": "turtle"},
                code="invalid_file"
            )

        namesp = namespaces_spkcspider.content["hashable/"]
        namesp_meta = namespaces_spkcspider.meta
        namesp_content = namespaces_spkcspider.content

        tmp = list(g.triples((None, namesp_meta.scope, None)))
        if len(tmp) != 1:
            raise forms.ValidationError(
                _("invalid graph, scopes: %(scope)s"),
                params={"scope": tmp},
                code="invalid_graph"
            )
        start = tmp[0][0]
        scope = tmp[0][2].value
        tmp = g.objects((start, namesp_meta.pages, None))
        if len(tmp) != 1:
            raise forms.ValidationError(
                _("invalid graph, pages: %(page)s"),
                params={"page": tmp},
                code="invalid_graph"
            )
        pages = tmp[0][2].value
        if pages != 1:
            raise forms.ValidationError(
                _("Multipage graphs not supported yet, sorry"),
                code="not_supported"
            )
        mtype = None
        if scope == "list":
            mtype = "UserComponent"
        else:
            mtype = list(g.triples(
                (
                    start, namesp_content.type, None
                )
            ))
            if len(mtype) > 0:
                mtype = mtype[0][2].value
            else:
                mtype = None

        self.cleaned_data["data_type"] = get_settings_func(
            "VERIFIER_CLEAN_GRAPH",
            "spkcspider.apps.verifier.functions.clean_graph"
        )(mtype, g)
        if not self.cleaned_data["data_type"]:
            raise forms.ValidationError(
                _(
                    "Invalid type: %(type)s"
                ),
                params={"type": mtype},
                code="invalid_type"
            )
            return

        hashes = [
            hash_entry(i) for i in
            chain(
                g.triples((None, namesp + "name", None)),
                g.triples((None, namesp + "value", None))
            )
        ]
        self.cleaned_data["linked_hashes"] = {}
        for i in g.triples((None, namesp + "url", None)):
            if (URIRef(i[2].value), None, None) in g:
                continue
            url = merge_get_url(i[2].value, raw="embed")
            if not settings.DEBUG and not url.startswith("https://"):
                raise forms.ValidationError(
                    _('Insecure url scheme: %(url)s'),
                    params={"url": url},
                    code="insecure_scheme"
                )
                return
            try:
                resp = requests.get(url, stream=True)
            except requests.exceptions.ConnectionError:
                raise forms.ValidationError(
                    _('invalid url: %(url)s'),
                    params={"url": url},
                    code="invalid_url"
                )
                return
            if resp.status_code != 200:
                raise forms.ValidationError(
                    _("Retrieval failed: %(reason)s"),
                    params={"reason": resp.reason},
                    code=str(resp.status_code)
                )
                return
            h = get_hashob()
            h.update(XSD.base64Binary.encode("utf8"))
            for chunk in resp.iter_content(BUFFER_SIZE):
                h.update(chunk)
            self.cleaned_data["linked_hashes"][i[2].value] = h.hexdigest()
            hashes.append(h.digest())

        for i in g.subjects(namesp + "id", None):
            h = get_hashob()
            h.update(i.encode("utf8"))
            hashes.append(h.digest())
        hashes.sort()

        h = get_hashob()
        for i in hashes:
            h.update(i)
        self.cleaned_data["hash"] = h.hexdigest()
        self.fields["linked_hashes"].initial = \
            self.cleaned_data["linked_hashes"]
        self.fields["hash"].initial = self.cleaned_data["hash"]
        self.fields["dvfile"].initial = self.cleaned_data["dvfile"]
        self.fields["data_type"].initial = self.cleaned_data["data_type"]

        return self.cleaned_data
