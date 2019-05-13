# flake8: noqa

from spkcspider.settings import *  # noqa: F403, F401

INSTALLED_APPS += [
    'spkcspider.apps.spider_filets',
    'spkcspider.apps.spider_keys',
    'spkcspider.apps.spider_tags',
    'spkcspider.apps.spider_webcfg',
    # ONLY for tests and REAL verifiers=companies verifing data
    'spkcspider.apps.verifier',
    'captcha'
]
USE_CAPTCHAS = True


# for tests
SPIDER_REQUEST_KWARGS_MAP["localhost"] = {
    "verify": False,
    "timeout": 1,
    "proxies": {}
}

# Verifier specific options, normally not required
# requests parameter overwrites
# * "hostname.foo": parameter for specific domain
# * "".foo": parameter for a tld
# * b"default": default parameters for request
# why binary? Because it cannot clash with a "default" host this way
# hierarchy: host > tld > b"default"
# NOTE: if VERIFIER_REQUEST_KWARGS_MAP is not specified
#       SPIDER_REQUEST_KWARGS_MAP is used
VERIFIER_REQUEST_KWARGS_MAP = {
    b"default": {
        "verify": certifi.where(),
        "timeout": 6,
        "proxies": {}
    },
    "localhost": {  # for tests
        "verify": False,
        "timeout": 1,
        "proxies": {}
    }
}
# how many verification requests of user/ip per minute
VERIFIER_REQUEST_RATE = "10/m"
# 40 mb maximal size
VERIFIER_MAX_SIZE_ACCEPTED = 40000000
# 2 mb, set to 0 to disable a direct file upload
VERIFIER_MAX_SIZE_DIRECT_ACCEPTED = 2000000

# not required, SpiderTokenAuthBackend have to be tested, so here active
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'spkcspider.apps.spider.auth.SpiderTokenAuthBackend'
]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '^_08u&*be(*my6$pv^m3fki!2s5)5e)9@l5l#srch1h)w3p+$l'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# how many user contents/components per page
SPIDER_OBJECTS_PER_PAGE = 3
# how many raw/serialized results per page?
SPIDER_SERIALIZED_PER_PAGE = 3
# max depth of references
SPIDER_MAX_EMBED_DEPTH = 5

CELERY_BROKER_URL = "redis://127.0.0.1:6379"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379"

# specify fixtures directory for tests
FIXTURE_DIRS = [
    "tests/fixtures/"
]
