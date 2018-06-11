Simple Public Key and Content Spider (short: spkcspider)
--------------------------------------------------------

spkcspider can manage your online data in a safe way:

Instead of storing your address data on every online shop, your address data is
saved in a spider component which you provide the online shop. This has following advantages:

* depending services like web stores doesn't save your private data
  This makes them easily DSGVO compatible without adjustments
* breaches contain only links to data (which can also be protected)
* Address Data have to changed only on one place if you move. This is especially useful if you move a lot
  Also if you travel and want to buy something on the way.
* Signing of Data possible.


# Help Wanted

The tool is not ready yet. An ugly prototype exists.
I am currently just a single developer. I could really use some help and together we will finish earlier

# Installation

This project can either be used as a standalone project (clone) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: only required for standalone project

# Thanks

Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
