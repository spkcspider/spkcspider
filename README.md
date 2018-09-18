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
* Verification of Data
* Privacy: private servers are easily set up (only requirement: cgi), compatible to tor
* Travelling: some people don't respect common rules for privacy. This allows to keep your life private. First you don't have it on the device, secondly you can hide it with the travel mode (against the worst kind of inspectors)
  * for governments: even you are civilized do you really want to expose your citizen to some untrusted countries? Will traveller from other countries accept getting exposed? The best compromise is to give people power over their data even it has certain disadvantages for you.
  * for users:
    * Note: traces could be still existent (like "recently-used" feature)


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders, you may want to use your own user model

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: contains spkcspider url detection and wsgi handler


Note: Mysql works with some special settings:
Set MYSQL_HACK = True and require mysql to use utf8 charset
To unbreak tests, use 'CHARSET': 'utf8':

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        ...
        'TEST': {
            'CHARSET': 'utf8'
        }
    }
}

```

Possibilities how to add utf8 charset to mysql:
* use 'read_default_file' and add "default-character-set = utf8" in config
* create database with "CHARACTER SET utf8"
* see: https://docs.djangoproject.com/en/dev/ref/databases/#mysql-notes


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

* add: create content, with AssignedContent form
* raw_add: not existent, can be archieved by return response
* update: update content
* raw_update: update Content, without AssignedContent form, adds second raw update mode
* export: export data (import not implemented yet)
* view: present usercontent to untrusted parties

## strength
* 0: no protection
* 1-4: protection which can be provided by protections
* 5: public attribute not set
* 6-9: protections + public attribute not set
* 10: index, can be used in combination with unique attribute to create a component unique to user


# External usage

There are some special GET parameters for services with special requirements:
* prefer_get=true: retrieve token as GET parameter
* token=xy: token as GET parameter, if invalid: refresh token
* raw=true: optimize output for machines
* raw=embed: embed content, for ContentList only
* id=id&id=id: limit content ids, for ContentList only
* search=foo: search case insensitive for string in info for lists only
* info=foo: search info tag in info for list only
* protection=false: fail if protections are required
* protection=xy&protection=yx...: protections to use
* [embed_big=true]: only staff and superuser can use it. Overrides maximal size of files which are embedded


verified_by urls should return hashname:hash_hexdigest

# TODO

* design: cleanup
  * use strength for coloring e.g. yellow 10, blue 0, the rest green tones (primive done)
* layout: verifiers+examples
* layout: cleanup defaults
* improve anchors
* tests

Later:
* create client side script for import (pushing to server, index token for auth?)
* textfilet
* hot reloading
* export protections and protection settings, Maybe?
* performance improvements
* import user content, usercomonents and usercontent
* log changes
* complete travel mode


# Thanks

Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
Some fields and TextField use Trumbowyg by Alexander
Django team for their excellent product 
