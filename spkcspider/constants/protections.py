"""
    Constants for protections and tokens
"""


__all__ = [
    "MAX_TOKEN_SIZE", "MAX_TOKEN_B64_SIZE", "MIN_PROTECTION_STRENGTH_LOGIN",
    "ProtectionType", "ProtectionStateType", "travel_scrypt_params"
]


import enum

MAX_TOKEN_SIZE = 90

if MAX_TOKEN_SIZE % 3 != 0:
    raise Exception("MAX_TOKEN_SIZE must be multiple of 3")

MAX_TOKEN_B64_SIZE = MAX_TOKEN_SIZE*4//3
MIN_PROTECTION_STRENGTH_LOGIN = 2
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
    # show password dialog
    password = "f"
    # forget about recovery, every recovery method is authentication
    # and will be misused this way
    # The only real recovery is by staff and only if there is a secret

    def __str__(self):
        # output value instead of member name
        return self.value


class ProtectionStateType(str, enum.Enum):
    disabled = "a"
    enabled = "b"
    instant_fail = "c"

    def __str__(self):
        # output value instead of member name
        return self.value

    @classmethod
    def as_choices(cls):
        from django.utils.translation import gettext_lazy as _
        return (
            (i[1], _(i[0].replace('_', ' ')))
            for i in ProtectionStateType.__members__.items()
        )
