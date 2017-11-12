#! /usr/bin/env python3
# -*- coding: UTF-8 -*-

from setuptools import setup, find_packages

install_requirements = [
    "django",
    "swapper",
    "jsonfield",

    #"pillow",
]

debug_requirements = [
    "Werkzeug",
    "pyOpenSSL",
    "django-extensions",
]

#install_requirements += debug_requirements

version=0.1

setup(name='spkbspider',
      version=version,
      license="MIT",
      zip_safe=False,
      platforms='Platform Independent',
      install_requires=install_requirements,
      extra_requires={
        "debug": debug_requirements
      },
      data_files=[('spkbspider', ['LICENSE'])],
      packages=["spkbspider", "spkbspider.apps.spider", "spkbspider.apps.spideraccounts", "spkbspider.apps.spiderbrokers", "spkbspider.apps.spiderkeys"],
      package_data={
        '': ['templates/**.*'],
        '': ['static/**.*'],
      },
      #ext_modules=distributions,
      test_suite="tests")
