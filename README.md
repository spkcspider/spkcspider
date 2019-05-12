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


## Build Requirements
* npm
* pip >=19 (and poetry)

## Poetry (within virtual environment)
~~~~ sh
poetry install
# for installing with extras specify -E extra1 -E extra2
~~~~

## Pip
~~~~ sh
pip install .
~~~~

## Setup
~~~~ sh
npm install --no-save
./manager.py migrate
./manager.py collectstatic
# or simply use
./tools/install_deps.sh
~~~~

## Caveats

Mysql works with some special settings:
Require mysql to use utf8 charset
To unbreak tests, use 'CHARSET': 'utf8':

~~~~ python
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
downgrade sqlite3 to 3.25 or upgrade django to at least 2.1.5/2.0.10

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

~~~~

# External usage

There are special GET parameters for controlling spkcspider:
* page=<int>: page number
* token=xy: token as GET parameter, if invalid: retrieve token as GET parameter
* token=prefer: uses invalid mechanic, easier to see what it does
* raw=true: optimize output for machines, use turtle format
* raw=embed: embed content of components
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
* strict infofield search can be activated with \_
* !!foo escapes a !foo item
* \_\_foo escapes a \_foo item
* !\_ negates a strict infofield search
* \_unlisted is a special search: it lists with "unlisted" marked contents

verified_by urls should return last verification date for a hash

## raw mode

raw mode can follow references even in other components because it is readonly.
Otherwise security could be compromised.

## Important Features

* Persistence: Allow referrer to save data (used and activated by persistent features)
* WebConfig: Allow remote websites and servers to save config data on your server (requires Persistence)
* TmpConfig: Allow remote websites and servers to save config data on your server, attached to temporary tokens (means: they are gone after a while)


# internal API


## Structure

### spider:
For spiders and contents

* spkcspider.apps.spider: store User Components, common base, WARNING: has spider_base namespace to not break existing apps
* spkcspider.apps.spider_accounts: user implementation suitable for the spiders. You can supply your own user model instead.
* spkcspider.apps.spider_filets: File and Text Content types
* spkcspider.apps.spider_keys: Public keys and anchors
* spkcspider.apps.spider_tags: verified information tags
* spkcspider.apps.spider_webcfg: WebConfig Feature
* spkcspider: contains spkcspider url detection and wsgi handler

### verifier:
Base reference implementation of a verifier.

spkcspider.apps.verifier: verifier base utils WARNING: has spider_verifier namespace to not break existing apps


## info field syntax

The info field is a simple key value storage. The syntax is (strip the spaces):

flag syntax: \\x1e key \\x1e
key value syntax: \\x1e key=value \\x1e

Note: I use the semantic ascii seperators \\x1e. Why? Sperating with an non-printable character eases escaping and sanitizing.
Note 2: I reverted from using \\x1f instead of = because the info field is used in searchs

Why not a json field? Django has no uniform json field for every db adapter yet.


## authentication/privileges

* request.is_staff: requesting user used staff rights to access view (not true in ComponentPublicIndex)
* request.is_owner: requesting user owns the components
* request.is_special_user: requesting user owns the components or is_staff
* request.protections: int: enough protections were fullfilled, maximal measured strength, list: protections which failed, False: no access; access with protections not possible

## Special Scopes

* add: create content, with AssignedContent form
* update: update content
* raw_update: update Content, without AssignedContent form, adds second raw update mode (raw_add is not existent, can be archieved by returning HttpResponse in add scope)
* export: export data (import not implemented yet)
* view: present content to untrusted parties

## strength (component)
* 0: no protection. Complete content visible
* 1-3: protection strength which can be provided by protections. Meta data (names, descriptions) visible, inclusion in sitemap, public components
* 4: login only, user password. Still with inclusion of metadata
* 5: public attribute not set. No inclusion in sitemap or public components index anymore
* 6-8: protections + public attribute not set
* 9: login only, user password + public attribute not set
* 10: index, login only, special protected. Protections are used for login. Content here can be made unique per user by using unique per component attribute

= extra["strength"] on token (if available elsewise treat as zero):

the strength of the usercomponent for which it was created at the creation point

## strength (protection)
* 0: no protection
* 1-3: weak, medium, strong
* 4: do component authentication

= extra["prot_strength"] on token (if available elsewise treat as zero):

the strength of protections which was passed for creating the token

Note: access tokens created by admin have strength 0

## get usercomponent/content from url/urlpart for features

Use UserComponent.from_url_part(url) / AssignedContent.from_url_part(url, [matchers]) for that
or use a domain_mode or persistent token.
Note: the difference between a domain_mode and a persistent token is, that the domain_mode token has a variable lifetime (user specific but defaults to 7 days)


# API Breaks
* >0.5: settings rename\*\_ TLD_PARAMS_MAPPING to \*\_REQUEST_KWARGS_MAP with new syntax (hosts are allowed, tlds start with .)
  * Note: port arguments are stripped, localhost matches localhost:80, localhost:8000, ...

# TODO
* examples
* documentation
* tests for other dbs than sqlite3 (and postgresql)
* Localisation
  * harmonize punctation
* pw protection: add migration tool for changed SECRET_KEY

## Later
* maybe: make quota type overridable (maybe add extra nonsaved quota: other or use 0)
* create client side script for import (pushing to server, index token for auth?)
  * use browerside javascript?
* textfilet hot reloading
* log changes
* improve protections, add protections

### Implement Emails/messaging
* email to spkcspider transport wrapper (also script)+component (encrypt, transparent gpg)
  * delta chat integration
  * webinterface
* implement webreferences
* WebReference on an "email" object is an "email"
* Webreferences can contain cache
* can optionally contain tags used for encryption and/or refcounting for automatic deletion


### Implement Web Comments
* every internal page can be annotated (to keep contact to author)
* reactions and likes
* you see only the comments of your friends
* implement with messaging? Would keep comments private
* Later/Maybe:
  * way to register your comment url on webpage, so others can see all comments
  * social media stuff: find content via comments and likes
  * annotation of other pages



# Thanks

* Default theme uses Font Awesome by Dave Gandy - http://fontawesome.io
* Some text fields use Trumbowyg by Alexander Demode
* Django team for their excellent product
