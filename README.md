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
* Travelling: some people don't respect common rules for privacy. This allows to keep your life private.
  * You don't have it on the device
  * You can hide your data with the travel mode (against the worst kind of inspectors)
    * Note: traces could be still existent (like "recently-used" feature)
  * for governments: the data can still be acquired on other ways. So why bothering the travel mode?


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

spkcspider.apps.spideraccounts: user implementation suitable for the spiders. You can supply your own user model instead.

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: contains spkcspider url detection and wsgi handler


## Requirements
* npm
* poetry or setuptools

## Poetry
~~~~.sh
poetry install
npm install
~~~~


## Poetry
~~~~.sh
poetry install
npm install
~~~~

## Caveats

Mysql works with some special settings:
Set MYSQL_HACK = True and require mysql to use utf8 charset
To unbreak tests, use 'CHARSET': 'utf8':

~~~~.python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        ...
        'TEST': {
            'CHARSET': 'utf8'
        }
    }
}

~~~~

Possibilities how to add utf8 charset to mysql:
* use 'read_default_file' and add "default-character-set = utf8" in config
* create database with "CHARACTER SET utf8"
* see: https://docs.djangoproject.com/en/dev/ref/databases/#mysql-notes


# API

Note: there are some migration breaks. Especially to unbreak mysql. Should not happen after tests are integrated


## authentication/privileges

* request.is_elevated_request:
  * Fullfilled if:
    * user has some privileges: owner, staff, admin
    * passed protections of strength >= MIN_STRENGTH_EVELATION = 2 by default
  * Purpose:
    * protect bad protected content


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
* token=xy: token as GET parameter, if invalid: retrieve token as GET parameter
* token=prefer: uses invalid mechanic, easier to see what it does
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

* link should contain token
* transfer with prefer_get token into GET
* layout: verifiers+examples
* fix search
* improve anchors
* tests

Later:
* create client side script for import (pushing to server, index token for auth?)
* email to spkcspider transport wrapper (also script)+component
* textfilet hot reloading
* log changes
* complete travel mode
* color tones for strength

# Thanks

* Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
* Some fields and TextField use Trumbowyg by Alexander Demode
* Django team for their excellent product
