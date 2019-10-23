# flake8: noqa

import os

from spkcspider.settings.debug import *  # noqa: F403, F401

SPIDER_INLINE = "SPIDER_NO_INLINE" in os.environ or None

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'spkcspider',
    'HOST': '',
  }
}
