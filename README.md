Simple Public Key and Content Spider (short: spkcspider)
--------------------------------------------------------


This project can either be used as a standalone project (clone) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkcspider.apps.spider: store User Components, common base, WARNING: has spiderucs namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider.spkcspider: only required for standalone project
