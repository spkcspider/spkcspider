__all__ = [
    "hex_size_of_bigid", "static_token_matcher", "host_tld_matcher",
    "TokenCreationError", "ProtectionResult", "ActionUrl", "protected_names"
]

import re
from collections import namedtuple

hex_size_of_bigid = 16


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


ActionUrl = namedtuple("ActionUrl", ["name", "url"])
protected_names = {"index"}
