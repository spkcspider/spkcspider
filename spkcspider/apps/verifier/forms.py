__all__ = ["CreateEntryForm"]

from itertools import chain
import logging

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
    h.update(triple[2].datatype.encode("ascii"))
    h.update(triple[2].value.encode("ascii"))
    return h.digest()


class CreateEntryForm(forms.ModelForm):
    url = forms.URLField(help_text=_source_url_help)

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
                        _('Insecure url scheme: %s') % url,
                        code="insecure_scheme"
                    )
                )
                return
            try:
                resp = requests.get(url, stream=True)
            except requests.exceptions.ConnectionError:
                self.add_error(
                    "url", forms.ValidationError(
                        _("invalid url: %s") % url,
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

            if not get_settings_func(
                "VERIFIER_VERIFY_LENGTH",
                "spkcspider.apps.verifier.functions.verify_length"
            )(resp):
                self.add_error(
                    "url", forms.ValidationError(
                        _(
                            "Retrieval failed, no length specified, invalid\n"
                            "or too long, length: %s"
                        ) % resp.headers.get("content-length", None),
                        code="invalid_length"
                    )
                )
                return
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
        try:
            g.parse(
                self.cleaned_data["dvfile"].temporary_file_path(),
                format="turtle"
            )
        except Exception as exc:
            logging.exception(exc)
            raise forms.ValidationError(
                _("not a \"%s\" file") % "turtle",
                code="invalid_file"
            )

        namesp = namespaces_spkcspider.content["hashable/"]
        namesp_meta = namespaces_spkcspider.meta
        namesp_content = namespaces_spkcspider.content

        start, scope = list(g.triples((None, namesp_meta.scope, None)))[:2]
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
                    "Invalid type: %s"
                ) % mtype,
                code="invalid_type"
            )
            return

        hashes = [
            hash_entry(i) for i in
            chain.from_iterables(
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
                    _('Insecure url scheme: %s') % url,
                    code="insecure_scheme"
                )
                return
            try:
                resp = requests.get(url, stream=True)
            except requests.exceptions.ConnectionError:
                raise forms.ValidationError(
                    _("invalid url: %s") % url,
                    code="invalid_url"
                )
                return
            if resp.status_code != 200:
                raise forms.ValidationError(
                    _("Retrieval failed: %s") % resp.reason,
                    code=str(resp.status_code)
                )
                return
            h = get_hashob()
            h.update(XSD.base64Binary)
            for chunk in resp.iter_content(BUFFER_SIZE):
                h.update(chunk)
            self.cleaned_data["linked_hashes"][i[2].value] = h.hexdigest()
            hashes.append(h.digest())

        for i in g.subjects(namesp + "id", None):
            h = get_hashob()
            h.update(i.encode("ascii"))
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
