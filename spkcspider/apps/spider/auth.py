from django.contrib.auth.backends import ModelBackend
from django.http import Http404
from django.utils import timezone

from .models import UserComponent, Protection, TravelProtection, AuthToken
from .constants import ProtectionType, TravelLoginType


class SpiderTokenAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, **kwargs):
        """ Use protections for authentication"""
        tokenstring = request.GET.get("token", None)
        if not tokenstring:
            return
        expire = timezone.now()-self.usercomponent.token_duration
        travel = TravelProtection.objects.get_active().filter(
            associated_rel__usercomponent__user__username=username
        ).exclude(login_protection=TravelLoginType.none.value)

        is_fake = False

        if travel.exists():
            uc = UserComponent.objects.filter(
                user__username=username, name="fake_index"
            ).first(),
            is_fake = True
        else:
            uc = UserComponent.objects.filter(
                user__username=username, name="index"
            ).first()

        # delete old token, so no confusion happen
        AuthToken.objects.filter(
            usercomponent=uc, created__lt=expire
        ).delete()
        if AuthToken.objects.filter(
            usercomponent=uc,
            token=tokenstring
        ).exists():
            request.session["is_fake"] = is_fake
            return uc.user


class SpiderAuthBackend(ModelBackend):

    def authenticate(self, request, username=None,
                     protection_codes=None, nospider=False, **kwargs):
        """ Use protections for authentication"""
        # disable SpiderAuthBackend backend (against recursion)
        if nospider:
            return
        travel = TravelProtection.objects.get_active().filter(
            associated_rel__usercomponent__user__username=username
        ).exclude(login_protection=TravelLoginType.none.value)
        uc = UserComponent.objects.filter(
            user__username=username, name="index"
        ).first()

        uc_fake = None
        if travel.exists():
            uc_fake = UserComponent.objects.filter(
                user__username=username, name="fake_index"
            ).first()
        try:
            if not uc:
                request.protections = Protection.authall(
                    request, scope="auth",
                    ptype=ProtectionType.authentication.value,
                    protection_codes=protection_codes
                )
                if request.protections is True:  # should never happen
                    return None
            else:
                if uc_fake:
                    request.protections = uc_fake.auth(
                        request, scope="auth",
                        ptype=ProtectionType.authentication.value,
                        protection_codes=protection_codes
                    )
                    if request.protections is True:
                        request.session["is_fake"] = True
                        return uc_fake.user
                protections = uc.auth(
                    request, scope="auth",
                    ptype=ProtectionType.authentication.value,
                    protection_codes=protection_codes
                )
                if protections is True:
                    request.protections = protections
                    request.session["is_fake"] = False
                    return uc.user
                # overwrite uc_fakes protections with cached protections
                if not uc_fake:
                    request.protections = protections
        except Http404:
            # for Http404 auth abort by protections (e.g. Random Fail)
            pass
