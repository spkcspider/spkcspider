__all__ = (
    "get_settings_func", "extract_app_dicts", "get_requests_params"
)

import inspect

from functools import lru_cache
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


from spkcspider.constants import host_tld_matcher


# for not spamming sets
_empty_set = frozenset()
# for not spamming dicts
_empty_dict = dict()


@lru_cache(maxsize=None)
def get_settings_func(*args, default=None, exclude=frozenset()):
    if default is None:
        names, default = args[:-1], args[-1]
    filterpath = None
    for name in names:
        if getattr(settings, name, None) is not None:
            filterpath = getattr(settings, name)
            break
    if filterpath is None:
        filterpath = default
    # note: cannot distinguish between False and 0 and True and 1
    if filterpath in exclude:
        raise ValueError("invalid setting")
    if callable(filterpath):
        return filterpath
    elif isinstance(filterpath, bool):
        return lambda *args, **kwargs: filterpath
    else:
        module, name = filterpath.rsplit(".", 1)
        return getattr(import_module(module), name)


def extract_app_dicts(app, name, fieldname=None):
    ndic = {}
    for (key, value) in getattr(app, name, _empty_dict).items():
        if inspect.isclass(value):
            if "{}.{}".format(
                value.__module__, value.__qualname__
            ) not in getattr(
                settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
            ):
                if fieldname:
                    setattr(value, fieldname, key)
                ndic[key] = value
        else:
            # set None if Module is not always available
            if value and value not in getattr(
                settings, "SPIDER_BLACKLISTED_MODULES", _empty_set
            ):
                module, name = value.rsplit(".", 1)
                value = getattr(import_module(module), name)
                if fieldname:
                    setattr(value, fieldname, key)
                ndic[key] = value
    return ndic


def get_requests_params(url):
    _url = host_tld_matcher.match(url)
    if not _url:
        raise ValidationError(
            _("Invalid URL: \"%(url)s\""),
            code="invalid_url",
            params={"url": url}
        )
    _url = _url.groupdict()
    mapper = settings.SPIDER_REQUEST_KWARGS_MAP
    return (
        mapper.get(
            _url["host"],
            mapper.get(
                _url["tld"],  # maybe None but then fall to retrieval 3
                mapper[b"default"]
            )
        ),
        get_settings_func(
            "SPIDER_INLINE",
            "spkcspider.apps.spider.functions.clean_spider_inline",
            exclude=frozenset({True})
        )(_url["host"])
    )
