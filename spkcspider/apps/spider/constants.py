
__all__ = ("ProtectionType", "UserContentType", "ProtectionResult")

import enum
from collections import namedtuple


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])


class ProtectionType(str, enum.Enum):
    # receives: request, scope
    access_control = "a"
    # receives: request, scope, password
    authentication = "b"
    # protections which can be used for reliable access (from machines)
    reliable = "c"
    # protections which does not contribute to required_passes (404 only)
    no_count = "d"
    # forget about recovery, every recovery method is authentication
    # and will be misused this way
    # The only real recovery is by staff and only if there is a secret


class UserContentType(str, enum.Enum):
    # can only be added to protected "index" usercomponent
    confidential = "a"
    # allow public attribute, incompatible with confidential
    public = "b"
    # update content is without form/for form updates it is not rendered
    raw_update = "c"
    # adding content renders no form, only raw output of render
    raw_add = "d"
    # allow links from non public usercomponents
    link_private = "e"
    # allow links from public usercomponents
    link_public = "f"
    # shortcut for link_private+link_public
    link = link_private+link_public
    # g not assigned

    # is content unique for usercomponent
    # together with confidential: unique for user
    unique = "h"
