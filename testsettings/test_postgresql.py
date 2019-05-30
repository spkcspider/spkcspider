# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401


DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'spkcspider',
    'HOST': '',
    # hopefully both fix travis tests
    'DISABLE_SERVER_SIDE_CURSORS': True,
    'ATOMIC_REQUESTS': True
  }
}
