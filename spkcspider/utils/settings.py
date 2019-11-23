__all__ = (
    "get_settings_func", "extract_app_dicts"
)

import inspect
from functools import lru_cache
from importlib import import_module

from django.conf import settings

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
    """

    """
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
                value = getattr(import_module(module, app.name), name)
                if fieldname:
                    setattr(value, fieldname, key)
                ndic[key] = value
    return ndic
