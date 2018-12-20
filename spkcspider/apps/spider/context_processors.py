__all__ = ("settings",)

from django.conf import settings as _settings


def settings(request):
    return {
        'SETTINGS': _settings,
    }
