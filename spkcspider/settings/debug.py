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

# Verifier specific options, not required
VERIFIER_ALLOW_FILE_UPLOAD = True
# 40 mb maximal size
VERIFIER_MAX_SIZE_ACCEPTED = 40000000

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


# how many user components per page
COMPONENTS_PER_PAGE = 3
# how many user contents per page
CONTENTS_PER_PAGE = 3
# how many raw/serialized results per page?
SERIALIZED_PER_PAGE = 3
# max depth of references
SERIALIZED_MAX_DEPTH = 5


CELERY_TASK_EAGER_PROPAGATES=True
CELERY_TASK_ALWAYS_EAGER=True
# this is a intentional bad documented debug backend
CELERY_BROKER_BACKEND='memory'

# specify fixtures directory for tests
FIXTURE_DIRS = [
    "tests/fixtures/"
]
