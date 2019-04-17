
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as CoreUserManager


class UserManager(CoreUserManager):
    def create_superuser(self, username, password, email=None, **extra_fields):
        # fix users with optional email
        super().create_superuser(username, email, password, **extra_fields)


# Create your models here.

def default_quota_spider_user_local():
    return getattr(settings, "SPIDER_USER_QUOTA_LOCAL", None)


def default_quota_spider_user_remote():
    return getattr(settings, "SPIDER_USER_QUOTA_REMOTE", None)


def default_quota_spider_user_components():
    return getattr(settings, "SPIDER_USER_QUOTA_USERCOMPONENTS", None)


class SpiderUser(AbstractUser):
    """ A reference User Implementation suitable for spkcspider """
    REQUIRED_FIELDS = []
    SAFE_FIELDS = ['email', 'password']
    if getattr(settings, 'ALLOW_USERNAME_CHANGE', False):
        SAFE_FIELDS.insert(0, 'username')

    # optional quota
    quota_local = models.PositiveIntegerField(
        null=True, blank=True, default=default_quota_spider_user_local,
        help_text=_("Quota in Bytes, null for no limit")
    )
    quota_remote = models.PositiveIntegerField(
        null=True, blank=True, default=default_quota_spider_user_remote,
        help_text=_("Quota in Bytes, null for no limit")
    )
    quota_usercomponents = models.PositiveIntegerField(
        null=True, blank=True, default=default_quota_spider_user_components,
        help_text=_("Quota in units, null for no limit")
    )
    # first_name,last_name are used in the UserForm so don't remove them
    # unless you want spending your time adapting the adminform

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'
