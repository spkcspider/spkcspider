#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
from setuptools import setup

base_dir = os.path.dirname(__file__)

install_requirements = [
    'django>=2',
    'django-simple-jsonfield',
    'certifi',
    'requests',
    'bleach',
    'rdflib',
    'html5lib',
    'cryptography',
    'django-widget-tweaks',
    'django-ranged-response',
    'django-next-prev',
    'lru-dict'
]

debug_requirements = [
    "Werkzeug",
    "pyOpenSSL",
    "django-extensions",
    "django-webtest",
    "django-simple-captcha",
    "WSGIProxy2",
    "celery",
    "sqlalchemy"
]

# install_requirements += debug_requirements


VERSIONING = {
    'root': '.',
    'version_scheme': 'guess-next-dev',
    'local_scheme': 'dirty-tag',
}

scm_stuff = {}
if os.path.exists(os.path.join(base_dir, ".git")):
    scm_stuff["setup_requires"] = ['setuptools_scm']
    scm_stuff["use_scm_version"] = VERSIONING

setup(
    name='spkcspider',
    license="MIT",
    zip_safe=False,
    platforms='Platform Independent',
    install_requires=install_requirements,
    extras_require={
        "debug": debug_requirements,
        "fcgi": ["flipflop"],
        "captcha": ["django-simple-captcha"],
        "mysql": ["mysqlclient"],
        "pgsql": ["psycopg-binary"],
        "celery": ["celery", "sqlalchemy"]
    },
    data_files=[('spkcspider', ['LICENSE'])],
    packages=[
        "spkcspider",
        "spkcspider.apps.spider",
        "spkcspider.apps.spider_accounts",
        "spkcspider.apps.spider_filets",
        "spkcspider.apps.spider_keys",
        "spkcspider.apps.spider_tags",
        "spkcspider.apps.spider_webcfg",
        "spkcspider.apps.verifier",
    ],
    package_data={
        '': ['templates/**.*', 'static/**'],
    },
    test_suite="tests",
    **scm_stuff
)
