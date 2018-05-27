#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

from setuptools import setup

install_requirements = [
    "django>=2",
    "jsonfield",
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
        "spkcspider.apps.spideraccounts", "spkcspider.apps.spidertags",
        "spkcspider.apps.spiderkeys"
      ],
      package_data={
        '': ['templates/**.*', 'static/**'],
      },
      test_suite="tests")
