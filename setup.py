#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

from setuptools import setup

install_requirements = [
    "django>=2",
    "django-simple-jsonfield",
]

debug_requirements = [
    "Werkzeug",
    "pyOpenSSL",
    "django-extensions",
]

# install_requirements += debug_requirements


VERSIONING = {
    'root': '.',
    'version_scheme': 'guess-next-dev',
    'local_scheme': 'dirty-tag',
}

setup(name='spkcspider',
      license="MIT",
      zip_safe=False,
      platforms='Platform Independent',
      install_requires=install_requirements,
      extra_requires={
        "debug": debug_requirements
      },
      use_scm_version=VERSIONING,
      setup_requires=['setuptools_scm'],
      data_files=[('spkcspider', ['LICENSE'])],
      packages=[
        "spkcspider", "spkcspider.apps.spider",
        "spkcspider.apps.spider_accounts", "spkcspider.apps.spider_tags",
        "spkcspider.apps.spider_keys"
      ],
      package_data={
        '': ['templates/**.*', 'static/**'],
      },
      test_suite="tests")
