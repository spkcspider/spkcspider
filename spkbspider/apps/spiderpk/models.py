from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy


from jsonfield import JSONField

# Create your models here.

class PublicKey(models.Model):
    key = models.TextField(null=True, unique=True)
    # can only be retrieved by hash
    hash = models.CharField(max_length=512, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    class Meta:
        indexes = [
            models.Index(fields=['hash']),
        ]


class UserComponent(models.Model):
    name = models.CharField(max_length=40)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    data = JSONField(default={})
    protections = models.ManyToManyField()
    class Meta:
        unique_together = [("user", "name"),]
        indexes = [
            models.Index(fields=['user', 'name']),
        ]
