#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

from setuptools import setup, find_packages

install_requirements = [
    "django>=2",
    #"swapper",
    "jsonfield",

    #"pillow",
]

debug_requirements = [
    "Werkzeug",
    "pyOpenSSL",
    "django-extensions",
]

#install_requirements += debug_requirements


VERSIONING = {
    'root': '.',
    'version_scheme': 'guess-next-dev',
    'local_scheme': 'dirty-tag',
}

setup(name='spkbspider',
      license="MIT",
      zip_safe=False,
      platforms='Platform Independent',
      install_requires=install_requirements,
      extra_requires={
        "debug": debug_requirements
      },
      use_scm_version=VERSIONING,
      setup_requires=['setuptools_scm'],
      data_files=[('spkbspider', ['LICENSE'])],
      packages=["spkbspider", "spkbspider.apps.spider", "spkbspider.apps.spideraccounts", "spkbspider.apps.spiderbrokers", "spkbspider.apps.spiderkeys"],
      package_data={
        '': ['templates/**.*'],
        '': ['static/**.*'],
      },
      #ext_modules=distributions,
      test_suite="tests")
