# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401
import os

SPIDER_INLINE = "SPIDER_NO_INLINE" in os.environ or None

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'spkcspider',
    'HOST': '',
  }
}
