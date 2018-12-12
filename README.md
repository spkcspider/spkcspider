Simple protection-knocking (visiting) card Spider (short: spkcspider)
--------------------------------------------------------

spkcspider provides a digital visiting card which can e.g. be used for authentication, shopping and payment. For this a multifactor authentication is provided.
It keeps your online data safe while shopping by just providing a link to a potion of your data. Doing this, the user may can provide some knocking mechanism (e.g. has to provide some code, tan) to protect the content.

Further features and advantages of spkcspider are:

* depending services like web stores need not tp save your private data
  This makes them easily DSGVO compatible without adjustments
  * doing so breaches contain only links to data (which can also be protected)
* Address Data have to changed only on one place if you move. This is especially useful if you move a lot
  Also if you travel and want to buy something on the way.
* Verification of data is possible.
* Privacy: private servers are easily set up (only requirement: cgi), compatible to tor
* Travelling: some people don't respect common rules for privacy. This tool allows you to keep your digital life private.
  * You don't have it on the device
  * You can hide your data with the travel mode (against the worst kind of inspectors)
    * Note: traces could be still existent (like "recently-used" feature, bookmarks)
  * for governments: the data can still be acquired by other ways. So why bothering the travel mode and trusting your inspectors blindly?


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

## spider:
For spiders and contents

spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps

spkcspider.apps.spideraccounts: user implementation suitable for the spiders. You can supply your own user model instead.

spkcspider.apps.spidertags: verified information tags and

spkcspider.apps.spiderkeys: store public keys

spkcspider: contains spkcspider url detection and wsgi handler

## verifier:
Base reference implementation of a verifier.

spkcspider.apps.verifier: verifier base utils WARNING: has spider_verifier namespace to not break existing apps



## Requirements
* npm
* poetry or setuptools

## Poetry
~~~~.sh
poetry install
npm install
~~~~

## Setuptools
~~~~.sh
pip install .
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
* 1-3: protection strength which can be provided by protections
* 4: login only, user password
* 5: public attribute not set
* 6-8: protections + public attribute not set
* 9: login only, user password + public attribute not set
* 10: index, can be used in combination with unique per component attribute for unique content per user

# External usage

There are some special GET parameters for services with special requirements:
* token=xy: token as GET parameter, if invalid: retrieve token as GET parameter
* token=prefer: uses invalid mechanic, easier to see what it does
* raw=true: optimize output for machines
* raw=embed: embed content
* id=id&id=id: limit content ids
* search=foo&search=!notfoo: search case insensitive a string
* info=foo&info=!notfoo: search info tag in info. Restricts search.
* protection=false: fail if protections are required
* protection=xy&protection=yx...: protections to use
* referrer=<url>: send token to referrer, client verifies with hash that he has control. Note: works only if strength > 0
* [embed_big=true]: only staff and superuser can use it. Overrides maximal size of files which are embedded

## search and info parameters

* search also searches UserComponents name and description fields
* can only be used with "list"-views
* items can be negated with !foo
* !!foo escapes a !foo item

verified_by urls should return last verification date for a hash

## raw mode

raw mode can follow references even in other components because it is readonly.
Otherwise security could be compromised.

# TODO
* examples
* tests
* documentation

## Later
* Localisation
* govAnchor
* create client side script for import (pushing to server, index token for auth?)
* email to spkcspider transport wrapper (also script)+component
* textfilet hot reloading
* log changes
* improve protections, add protections

# Thanks

* Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
* Some fields and TextField use Trumbowyg by Alexander Demode
* Django team for their excellent product
