Simple Public Key and Broker Spider (short: spkbspider)
-----------------------------------


This project can either be used as a standalone project (clone) or as a set of reusable apps (setup.py installation).

spkbspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkbspider.apps.spider: store User Components, base, WARNING: appears under spiderucs, with swappable setting SPIDERUCS_USERCOMPONENT_MODEL

spkbspider.apps.spiderbrokers: broker

spkbspider.apps.spiderkeys: store public keys

spkbspider.spkbspider: only required for standalone project
