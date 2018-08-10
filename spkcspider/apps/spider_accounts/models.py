from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as CoreUserManager


class UserManager(CoreUserManager):
    def create_superuser(self, username, password, email=None, **extra_fields):
        # fix users with optional email
        super().create_superuser(username, email, password, **extra_fields)


# Create your models here.


class SpiderUser(AbstractUser):
    REQUIRED_FIELDS = []
    SAFE_FIELDS = ['username', 'email', 'password']

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'

    # def get_absolute_url(self):
    #    return reverse_lazy()
