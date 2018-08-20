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
* Travelling: don't expose your life to untrusted thirdparty,
  no client side storage except sessions and "recently used"-feature of browser


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: contains spkcspider url detection and wsgi handler

# API

## authentication/privileges
* request.is_priv_requester: is private/privileged access. Fullfilled if:
  * is privileged: user, staff, admin
  * non public
  * protections were fullfilled? Maybe later, needs design
* request.is_owner: requesting user owns the components
* request.protections: True: enough protections were fullfilled, list: protections which failed, False: no access

## Special Scopes
* add: create usercomponent/Cpntent, with AssignedContent form
* add_raw: create usercomponent/Content, without AssignedContent form
* update: update Content
* update_raw: update Content without, without AssignedContent form
* export: later, not finished
* view: present usercontent to untrusted parties

# External usage

There are some special GET parameters for services with special requirements:
* prefer_get=true: retrieve token as GET parameter
, token=xy: token as GET parameter, if invalid refresh token
* raw=true: optimize output for machines
* protection=false: fail if protections are required
* protection=xy&protection=yx...: protections to use

verified_by urls should return hashname:hash_hexdigest

# TODO

* textfilet: add what you see is what you get js stuff
* layout: verifiers+examples
* layout: cleanup defaults
* export/import from usercomponents+user profiles => zip, security
* spider_keys: login stuff, oauth? PublicKey ident? secrets? survives dns name changes?

Later:
* travelmode: disable cache and "recently used" completely, needs design
* tags, nonces: may add to tag data a secret nonce, but it has to be portable
* log changes

# Thanks

Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
