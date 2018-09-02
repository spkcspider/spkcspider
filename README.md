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
* Privacy: private servers are easily set up (only requirement: cgi), compatible to tor
* Travelling: don't expose your life to untrusted thirdparty, don't have it on your device
  Note: traces could be still existent (like "recently-used" feature or cache)


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: contains spkcspider url detection and wsgi handler


Note: Mysql works maybe. Set MYSQL_HACK = True and fix the errors manually in the db.
Better use postgresql or sqlite.


Note: there are some migration breaks. Especially to unbreak mysql. Should not happen after tests are integrated


# API

## authentication/privileges

* request.is_priv_requester: is private/privileged access. Fullfilled if:
  * is privileged: user, staff, admin
  * non public
  * protections were fullfilled? Maybe later, needs design
* request.is_owner: requesting user owns the components
* request.protections: True: enough protections were fullfilled, list: protections which failed, False: no access, no matter what

## Special Scopes

* add: create usercomponent/Cpntent, with AssignedContent form
* add_raw: create usercomponent/Content, without AssignedContent form
* update: update Content
* update_raw: update Content, without AssignedContent form
* export: export data (import not finished)
* view: present usercontent to untrusted parties

# External usage

There are some special GET parameters for services with special requirements:
* prefer_get=true: retrieve token as GET parameter
* token=xy: token as GET parameter, if invalid: refresh token
* raw=true: optimize output for machines
* raw=embed: embed content, for ContentList only
* id=id&id=id: limit tp ids, for ContentList only
* search=foo: search case insensitive for string in info for lists only
* info=foo: search info tag in info for list only
* protection=false: fail if protections are required
* protection=xy&protection=yx...: protections to use
* deref=true: dereference references to other content (link, tags)

verified_by urls should return hashname:hash_hexdigest

# TODO

* design: cleanup
* textfilet
  * add what you see is what you get js stuff
  * hot reloading
* layout: verifiers+examples
* layout: cleanup defaults
* improve anchors
* tests

Later:
* export protections and protection settings, Maybe?
* performance improvements
* import user content, usercomonents and usercontent
* travelling protection: disable access till a timepoint
* travelmode: disable cache and "recently used" completely,
  maybe: limit components, needs design
  => extra app
* log changes
* calculate protection strength


# Thanks

Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
