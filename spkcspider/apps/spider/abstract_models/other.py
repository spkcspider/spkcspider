
__all__ = [
    "BaseSubUserModel"
]

from django.db import models


class BaseSubUserModel(models.Model):

    class Meta:
        abstract = True

    @property
    def user(self):
        return self.usercomponent.user  # pylint: disable=no-member

    @property
    def username(self):
        return self.usercomponent.username  # pylint: disable=no-member
