from django.contrib.auth.models import AbstractUser

# Create your models here.


class SpiderUser(AbstractUser):
    REQUIRED_FIELDS = []

    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'

    # def get_absolute_url(self):
    #    return reverse_lazy()
