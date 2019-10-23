__all__ = (
    "merge_get_url", "extract_host"
)

import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

_check_scheme = re.compile(r'^[a-z]+://', re.I)


def extract_host(url):
    url = url.lstrip(":/")
    if _check_scheme.search(url) is None:
        urlparsed = urlsplit("://".join(("https", url)))
    else:
        urlparsed = urlsplit(url)
    return "://".join(urlparsed[:2])


def merge_get_url(_url, **kwargs):
    if not _url.isprintable():
        raise ValidationError(
            _("Url contains control characters"),
            code="control_characters"
        )
    _url = _url.lstrip(":/")
    if _check_scheme.search(_url) is None:
        urlparsed = urlsplit("://".join(("https", _url)))
    else:
        urlparsed = urlsplit(_url)
    _strip = []
    for i in kwargs.keys():
        if not kwargs[i]:
            _strip.append(i)
    GET = parse_qs(urlparsed.query)
    GET.update(kwargs)
    for item in _strip:
        GET.pop(item, None)
    ret = urlunsplit((*urlparsed[:3], urlencode(GET, doseq=True), ""))
    return ret
