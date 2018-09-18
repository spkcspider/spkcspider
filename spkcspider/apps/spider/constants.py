
__all__ = (
    "ProtectionType", "UserContentType", "ProtectionResult",
    "TravelLoginType"
)

import enum
from collections import namedtuple


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])


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


class UserContentType(str, enum.Enum):
    # a, b not required anymore
    # update content is without form/for form updates it is not rendered
    # required for still beeing able to update elemental parameters
    raw_update = "c"
    # raw_add not required, archieved by returning response
    # d,e,f,g not assigned

    # is content unique for usercomponent
    # together with confidential: unique for user
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
