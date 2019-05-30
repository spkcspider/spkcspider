# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401

import os

CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my.cnf")

SPIDER_DISABLE_FAKE_CLIENT = "SPIDER_NO_INLINE" in os.environ

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'read_default_file': CONF_FILE,
        },
        'TEST': {
            'CHARSET': 'utf8'
        }
    }
}
