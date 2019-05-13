
__all__ = (
    "ProtectionType", "VariantType", "ProtectionResult",
    "MIN_PROTECTION_STRENGTH_LOGIN",
    "TravelLoginType", "MAX_TOKEN_SIZE", "MAX_TOKEN_B64_SIZE",
    "hex_size_of_bigid", "TokenCreationError", "protected_names", "spkcgraph",
    "dangerous_login_choices", "ActionUrl", "static_token_matcher",
    "host_tld_matcher", "travel_scrypt_params"
)

import enum
from collections import namedtuple
import re

from rdflib.namespace import Namespace


spkcgraph = Namespace("https://spkcspider.net/static/schemes/spkcgraph#")
# Literal allows arbitary datatypes, use this and don't bind

hex_size_of_bigid = 16

MAX_TOKEN_SIZE = 90

if MAX_TOKEN_SIZE % 3 != 0:
    raise Exception("MAX_TOKEN_SIZE must be multiple of 3")

MAX_TOKEN_B64_SIZE = MAX_TOKEN_SIZE*4//3


MIN_PROTECTION_STRENGTH_LOGIN = 2


# user can change static token but elsewise the token stays static
static_token_matcher = re.compile(
    r"(?:[^?]*/|^)(?P<static_token>[^/?]+)/(?P<access>[^/?]+)"
)

host_tld_matcher = re.compile(
    r'^[^.]*?(?!\.)(?P<host>[^/?:]+?(?P<tld>\.[^/?:.]+)?)(?=[/?:]|$)(?!:/)'
)


class TokenCreationError(Exception):
    pass


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])
ActionUrl = namedtuple("ActionUrl", ["url", "name"])
protected_names = {"index"}


travel_scrypt_params = {
    "length": 32,
    "n": 2**14,
    "r": 16,
    "p": 2
}


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
    # don't appear in allowed_content in contrast to feature except
    #   if specified with a feature
    #   here it unlists the contentvariant from public feature list
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
    # don't show protected contents and components
    hide = "a"
    # switches to hiding if trigger was activated
    trigger_hide = "b"
    # disable login
    disable = "c"
    # disable login if triggered
    trigger_disable = "C"
    # wipe travel protected contents and components
    # Note: noticable if shared contents are removed
    wipe = "d"
    # wipe user, self destruct user on login, Note: maybe noticable
    wipe_user = "e"


dangerous_login_choices = (
    TravelLoginType.wipe.value,
    TravelLoginType.wipe_user.value
)
