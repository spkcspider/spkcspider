__all__ = (
    "get_hashob", "aesgcm_scrypt_cryptor", "aesgcm_pbkdf2_cryptor",
    "calculate_protection_strength", "create_b64_token", "create_b64_id_token"
)

import base64
import logging
import os
from hashlib import pbkdf2_hmac
from statistics import mean

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes
from django.utils.translation import gettext_lazy as _
from spkcspider.constants import MAX_TOKEN_SIZE
from spkcspider.constants.protections import ProtectionStateType

logger = logging.getLogger(__name__)

_pbkdf2_params = {
    "iterations": 120000,
    "hash_name": "sha512",
    "dklen": 32
}

_Scrypt_params = {
    "length": 32,
    "n": 2**14,
    "r": 16,
    "p": 2
}


def get_hashob():
    return hashes.Hash(
        settings.SPIDER_HASH_ALGORITHM, backend=default_backend()
    )


def aesgcm_scrypt_cryptor(pw, salt=None, params=_Scrypt_params):
    if salt is None:
        salt = settings.SECRET_KEY
    salt = force_bytes(salt)

    return AESGCM(
        Scrypt(
            salt=salt,
            backend=default_backend(),
            **params
        ).derive(pw[:128].encode("utf-8"))
    )


def aesgcm_pbkdf2_cryptor(pw, salt=None, params=_pbkdf2_params):
    if salt is None:
        salt = settings.SECRET_KEY
    salt = force_bytes(salt)

    return AESGCM(
        pbkdf2_hmac(
            password=pw[:128].encode("utf-8"),
            salt=salt,
            **params
        )
    )


def calculate_protection_strength(required_passes, protections=None):
    prot_strength = None
    max_prot_strength = 0
    if protections:
        # instant fail strength
        fail_strength = 0
        amount = 0
        # regular protections strength
        strengths = []
        for protection in protections:
            state = protection.cleaned_data.get(
                "state", ProtectionStateType.disabled
            )
            if state == ProtectionStateType.disabled:
                continue
            if not protection.is_valid():
                continue

            if len(str(protection.cleaned_data)) > 100000:
                raise ValidationError(
                    _("Protection >100 kb: %(name)s"),
                    params={"name": protection}
                )
            if state == ProtectionStateType.instant_fail:
                s = protection.get_strength()
                if s[1] > max_prot_strength:
                    max_prot_strength = s[1]
                fail_strength = max(
                    fail_strength, s[0]
                )
            else:
                s = protection.get_strength()
                if s[1] > max_prot_strength:
                    max_prot_strength = s[1]
                strengths.append(s[0])
            amount += 1
        strengths.sort()
        if required_passes > 0:
            if amount == 0:
                # login or token only
                # not 10 because 10 is also used for uniqueness
                prot_strength = 4
            else:
                # avg strength but maximal 3,
                # (4 can appear because of component auth)
                # clamp
                prot_strength = min(round(mean(
                    strengths[:required_passes]
                )), 3)
        else:
            prot_strength = 0
        prot_strength = max(prot_strength, fail_strength)
    return (prot_strength, max_prot_strength)


def create_b64_token(size=None):
    if not size:
        from django.conf import settings
        size = getattr(settings, "TOKEN_SIZE", 30)
    if size > MAX_TOKEN_SIZE:
        logger.warning("Nonce too big")
    return base64.urlsafe_b64encode(
        os.urandom(size)
    ).decode('ascii').rstrip("=")


def create_b64_id_token(id, sep="_", size=None):
    return sep.join((hex(id)[2:], create_b64_token(size)))
