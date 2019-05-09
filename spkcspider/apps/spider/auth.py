
import logging
import random
import os
import time

from django.contrib.auth.backends import ModelBackend
from django.http import Http404
from django.utils import timezone

import ratelimit

from .models import UserComponent, Protection, TravelProtection, AuthToken
from .constants import (
    ProtectionType, MIN_PROTECTION_STRENGTH_LOGIN,
)

logger = logging.getLogger(__name__)

# seed with real random
_nonexhaustRandom = random.Random(os.urandom(30))


class SpiderTokenAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, **kwargs):
        """ Use protections for authentication"""
        tokenstring = request.GET.get("token", None)
        if not tokenstring:
            return

        now = timezone.now()

        token = AuthToken.objects.filter(
            usercomponent__name="index",
            token=tokenstring
        ).first()
        if token:
            uc = token.usercomponent
            if token.persist == -1 and token.created < now - uc.token_duration:
                token.delete()
                return
            if TravelProtection.objects.auth(request, uc, now):
                return uc.user


class SpiderAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, nospider=False, **kwargs):
        """ Use protections for authentication"""
        # disable SpiderAuthBackend backend (against recursion)
        if nospider:
            return
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()
        if not uc:
            request.protections = Protection.authall(
                request, scope="auth",
                ptype=ProtectionType.authentication.value,
                protection_codes=protection_codes
            )
            if type(request.protections) is int:  # should never happen
                logger.warning(
                    "Login try without username, should never "
                    "happen, archieved strength: %s",
                    request.protections
                )
                return None
        else:
            try:
                request.protections = uc.auth(
                    request, scope="auth",
                    ptype=ProtectionType.authentication.value,
                    protection_codes=protection_codes
                )
            except Http404:
                # for Http404 auth abort by protections (e.g. Random Fail)
                pass

            if type(request.protections) is int:
                if TravelProtection.objects.auth(request, uc):
                    if request.protections < MIN_PROTECTION_STRENGTH_LOGIN:
                        logger.warning(
                            "Low login protection strength: %s, %s",
                            request.protections, username
                        )
                    return uc.user
        # error path

        # allow blocking per hour
        ratelimit.get_ratelimit(
            request=request, group="spider_login_failed_ip", key="ip",
            inc=True, rate=(float("inf"), 3600)
        )
        ratelimit.get_ratelimit(
            request=request, group="spider_login_failed_account",
            key=lambda x, y: username, inc=True, rate=(float("inf"), 3600)
        )
        # be less secure here, most probably the user is already known
        time.sleep(_nonexhaustRandom.random()/2)
