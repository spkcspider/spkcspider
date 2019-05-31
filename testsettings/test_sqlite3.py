# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPIDER_INLINE = "SPIDER_NO_INLINE" in os.environ or None

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
