
__all__ = (
    "ProtectionType", "VariantType", "ProtectionResult",
    "TravelLoginType", "MAX_TOKEN_SIZE", "MAX_TOKEN_B64_SIZE",
    "hex_size_of_bigid",
    "TokenCreationError", "index_names", "protected_names", "spkcgraph",
    "dangerous_login_choices", "ActionUrl"
)

import enum
from collections import namedtuple

from rdflib.namespace import Namespace


spkcgraph = Namespace("https://spkcspider.net/static/schemes/spkcgraph#")
# Literal allows arbitary datatypes, use this and don't bind

hex_size_of_bigid = 16

MAX_TOKEN_SIZE = 90

if MAX_TOKEN_SIZE % 3 != 0:
    raise Exception("MAX_TOKEN_SIZE must be multiple of 3")

MAX_TOKEN_B64_SIZE = MAX_TOKEN_SIZE*4//3


class TokenCreationError(Exception):
    pass


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])
ActionUrl = namedtuple("ActionUrl", ["url", "name"])
index_names = ["index", "fake_index"]
protected_names = ["index", "fake_index"]


class ProtectionType(str, enum.Enum):
    # receives: request, scope
    access_control = "a"
    # receives: request, scope, password
    authentication = "b"
    # c: former reliable, no meaning
    # protections which does not contribute to required_passes (404 only)
    no_count = "d"
    # protections which have side effects
    side_effects = "e"
    # forget about recovery, every recovery method is authentication
    # and will be misused this way
    # The only real recovery is by staff and only if there is a secret


class VariantType(str, enum.Enum):
    # a not assigned
    # use persistent token
    #  can be used for some kind of federation
    #  warning: if token is deleted persisted content is deleted
    persist = "b"
    # update content is without form/for form updates it is not rendered
    # required for still beeing able to update elemental parameters
    raw_update = "c"
    # raw_add not required, archieved by returning response

    # don't list as contentvariant for user (for computer only stuff)
    #  works like unlisted in info field, just for ContentVariants
    # don't appear in allowed_content in contrast to feature
    # => should either depend on feature or normal content
    unlisted = "d"
    # activates domain mode
    domain_mode = "e"
    # allow outside applications push content to spiders
    # adds by default unlisted attribute
    # appears in features of userComponent
    # counts as foreign content
    # don't list as content variant for user
    component_feature = "f"
    # same, but assigns to contents
    content_feature = "g"

    # is content unique for usercomponent
    # together with strength level 10: unique for user
    unique = "h"
    # can be used as anchor, hash is automatically embedded
    anchor = "i"


class TravelLoginType(str, enum.Enum):
    # no protection, login works as usual
    none = "a"
    # experimental, creates a fake subset view
    fake_login = "b"
    # wipe travel protected data and index as soon as login occurs
    # Note: noticable if shared contents are removed
    wipe = "c"
    # wipe user, self destruct user on login, Note: maybe noticable
    wipe_user = "d"


dangerous_login_choices = (
    TravelLoginType.fake_login.value,
    TravelLoginType.wipe.value,
    TravelLoginType.wipe_user.value
)
