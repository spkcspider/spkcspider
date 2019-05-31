# flake8: noqa

from spkcspider.settings.debug import *  # noqa: F403, F401

import os

CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my.cnf")

SPIDER_INLINE = "SPIDER_NO_INLINE" in os.environ or None

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
