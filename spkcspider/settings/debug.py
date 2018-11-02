# flake8: noqa

from spkcspider.settings import *  # noqa: F403

INSTALLED_APPS += [
    'spkcspider.apps.spider_filets',
    'spkcspider.apps.spider_keys',
    'spkcspider.apps.spider_tags',
    # ONLY for tests and REAL verifiers=companies verifing data
    'spkcspider.apps.verifier',
]

# Verifier specific options, not required
AUTO_INCLUDE_VERIFIER = True
VERIFIER_ALLOW_FILE_UPLOAD = True
VERIFIER_MAX_SIZE_ACCEPTED = 40000000


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
