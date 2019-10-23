__all__ = ["get_requests_params"]


from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from spkcspider.constants import host_tld_matcher
from spkcspider.utils.settings import get_settings_func


def get_requests_params(url):
    _url = host_tld_matcher.match(url)
    if not _url:
        raise ValidationError(
            _("Invalid URL: \"%(url)s\""),
            code="invalid_url",
            params={"url": url}
        )
    _url = _url.groupdict()
    mapper = getattr(
        settings, "VERIFIER_REQUEST_KWARGS_MAP",
        settings.SPIDER_REQUEST_KWARGS_MAP
    )
    return (
        mapper.get(
            _url["host"],
            mapper.get(
                _url["tld"],  # maybe None but then fall to retrieval 3
                mapper[b"default"]
            )
        ),
        get_settings_func(
            "VERIFIER_INLINE", "SPIDER_INLINE",
            "spkcspider.apps.spider.functions.clean_spider_inline",
            exclude=frozenset({True})
        )(_url["host"])
    )
