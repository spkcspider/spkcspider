Simple protection-knocking (visiting) card Spider (short: spkcspider)
--------------------------------------------------------

spkcspider provides a digital visiting card which can e.g. be used for authentication, shopping and payment. For this a multifactor authentication is provided.
It keeps your online data safe while shopping by just providing a link to a potion of your data. Doing this, the user may can provide some knocking mechanism (e.g. has to provide some code, tan) to protect the content.

Further features and advantages of spkcspider are:

* cross device configuration without saving user data on webshop/service.
  This makes them easily DSGVO compatible without adjustments
* Address Data have to changed only on one place if you move. This is especially useful if you move a lot
  Also if you travel and want to buy something on the way.
* Verification of data is possible.
* Privacy: private servers are easily set up (only requirement: cgi), also compatible to tor
* Travelling: some people don't respect common rules for privacy. This tool allows you to keep your digital life private.
  * You don't have it on the device
  * You can hide your data with the travel mode (against the worst kind of inspectors)
    * Note: traces could be still existent (like "recently-used" feature, bookmarks)
  * for governments: use psychology instead of breaking into systems! The only victims are law-abidding citizens.


# Installation

This project can either be used as a standalone project (clone repo) or as a set of reusable apps (setup.py installation).

## spider:
For spiders and contents

* spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps
* spkcspider.apps.spider_accounts: user implementation suitable for the spiders. You can supply your own user model instead.
* spkcspider.apps.spider_filets: File and Text Content types
* spkcspider.apps.spider_keys: Public keys and anchors
* spkcspider.apps.spider_tags: verified information tags
* spkcspider.apps.spider_webcfg: WebConfig Feature
* spkcspider: contains spkcspider url detection and wsgi handler

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

### Possibilities how to add utf8 charset to mysql:
* use 'read_default_file' and add "default-character-set = utf8" in config
* create database with "CHARACTER SET utf8"
* see: https://docs.djangoproject.com/en/dev/ref/databases/#mysql-notes


### \_\_old crashes object creation:
downgrade sqlite3 to 3.25 or upgrade django to 2.1.5/2.0.10

importing data:

set:
UPDATE_DYNAMIC_AFTER_MIGRATION = False
before importing data (with loaddata), update dynamic creates data

### keep pathes if switching from cgi
~~~~
location /cgi-bin/cgihandler.fcgi {
   rewrite /cgi-bin/cgihandler.fcgi/?(.*)$ https://new.spkcspider.net/$1 redirect ;
}
~~~~

### logging
In this model tokens are transferred as GET parameters. Consider disabling the
logging of GET parameters (at least the sensible ones) or better:
disable logging of succeeding requests


nginx filter tokens only (hard):
~~~~
location / {
  set $filtered_request $request;
  if ($filtered_request ~ (.*)token=[^&]*(.*)) {
      set $filtered_request $1token=****$2;
  }
}
log_format filtered_combined '$remote_addr - $remote_user [$time_local] '
                    '"$filtered_request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent"';

access_log /var/logs/nginx-access.log filtered_combined;
~~~~

nginx filter GET parameters:
~~~~
log_format filtered_combined '$remote_addr - $remote_user [$time_local] '
                    '"$uri" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent"';

access_log /var/logs/nginx-access.log filtered_combined;
~~~~

apache filter GET parameters:
~~~~
LogFormat "%h %l %u %t \"%m %U %H\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"" combined

~~~

# API

## authentication/privileges

* request.is_staff: requesting user used staff rights to access view (not true in ComponentPublicIndex)
* request.is_owner: requesting user owns the components
* request.is_special_user: requesting user owns the components or is_staff
* request.protections: int: enough protections were fullfilled, maximal measured strength, list: protections which failed, False: no access; access with protections not possible

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
* raw=true: optimize output for machines, use turtle format
* raw=embed: embed content
* id=id&id=id: limit content ids (Content lists only)
* search=foo&search=!notfoo: search case insensitive a string
* search=\_unlisted: List "unlisted" content if owner, special user (doesn't work in public list).
* protection=false: fail if protections are required
* protection=xy&protection=yx...: protections to use
* intention=auth: try to login with UserComponent authentication (falls back to login redirect)
* referrer=<url>: activate referrer mode
  * intention=domain: domain verify referrer mode
  * intention=sl: server-less referrer mode
  * payload=<foo>: passed on successfull requests (including post), e.g. for sessionid
  * intention=login: referrer uses spkcspider for login (note: referrer should be the one where the user is logging in, check referrer field for that)
  * intention=persist: referrer can persist data on webserver
* embed_big=true: only for staff and superuser: Overrides maximal size of files which are embedded in graphs (only for default helper)

## Referrer
* normal referrer mode: send token to referrer, client verifies with hash that he sent the token.
* server-less referrer mode (sl): token is transferred as GET parameter and no POST request is made (less secure as client sees token and client is not authenticated)
* domain referrer mode (domain): referrer domain is add to token. Doesn't work with other intentions (but "live" mode is active as no filter will be created) and works only if domain_mode is for context active (e.g. feature or access context (content)). Can be automated, doesn't require user approval. Useful for tag updates (only active if feature requests domain mode).

## search parameters

* search also searches UserComponents name and description fields
* can only be used with "list"-views
* items can be negated with !foo
* strict infofield search can be activated with _
* !!foo escapes a !foo item
* \_\_foo escapes a \_foo item
* != negates a strict infofield search
* \_unlisted is a special search: it lists with "unlisted" marked contents

verified_by urls should return last verification date for a hash

## raw mode

raw mode can follow references even in other components because it is readonly.
Otherwise security could be compromised.

## Important Features

* Persistence: Allow referrer to save data (used and activated by persistent features)
* WebConfig: Allow remote websites and servers to save config data on your server (requires Persistence)


# TODO
* examples
* documentation
* layouts
* tests for other dbs
* improve default tag validators to prevent ddos gadgets by weak validators

## Later
* use django-cte (common table expressions)
  * maybe: relax attached_to_content restriction
* make quota type overridable (maybe add extra nonsaved quota: other or use 0)
* Localisation
* govAnchor
* messages instead error
* create client side script for import (pushing to server, index token for auth?)
* textfilet hot reloading
* log changes
* improve protections, add protections
* Travelprotection


### Implement Web Comments
* every webpage can be annotated
* reactions and likes
* you see only the comments of your friends
* Later/Maybe:
  * way to register your comment url on webpage, so others can see all comments
  * social media stuff: find content via comments and likes

### Implement Emails/messaging
* email to spkcspider transport wrapper (also script)+component (encrypt, transparent gpg)
  * delta chat integration
* implement webreferences
* WebReference on an "email" object is an "email"
* Webreferences can contain cache
* can optionally contain tags used for encryption and/or refcounting for automatic deletion

### re-implement TravelProtection
* hide contents
* remove fake_index?
* also: harden pws


# Thanks

* Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
* Some text fields use Trumbowyg by Alexander Demode
* Django team for their excellent product
