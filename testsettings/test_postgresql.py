# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401


DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'spkcspider',
    'HOST': ''
  }
}
