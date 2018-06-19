__all__ = ("is_registration_open",)

from django.conf import settings


def is_registration_open(request):
    return {
        'OPEN_FOR_REGISTRATION': getattr(
            settings, "OPEN_FOR_REGISTRATION", False
        ),
    }
