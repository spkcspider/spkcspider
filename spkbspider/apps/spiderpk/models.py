from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy


from jsonfield import JSONField

# Create your models here.
from .protections import Protection

class PublicKey(models.Model):
    key = models.TextField(null=True, unique=True)
    # can only be retrieved by hash
    hash = models.CharField(max_length=512, unique=True, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    class Meta:
        indexes = [
            models.Index(fields=['hash']),
        ]

class UserComponent(models.Model):
    name = models.CharField(max_length=40, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    data = JSONField(default={}, null=False)
    # should be used
    assigned = None
    protections = models.ManyToManyField(Protection, through=AssignedProtection, limit_choices_to=Protection.objects.valid())
    class Meta:
        unique_together = [("user", "name"),]
        indexes = [
            models.Index(fields=['user', 'name']),
        ]
