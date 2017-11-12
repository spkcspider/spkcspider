from django.db import models
from django.conf import settings
from django.utils.translation import pgettext_lazy

from jsonfield import JSONField
import swapper

import logging

logger = logging.getLogger(__name__)


# Create your models here.
from .signals import validate_success


class AbstractUserComponent(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    name = models.SlugField(max_length=50, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, editable=False)
    #data for requester (NOT FOR PROTECTION)
    data = JSONField(default={}, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)
    brokers = None
    publickeys = None
    # should be used for retrieving active protections, related_name
    assigned = None
    protections = models.ManyToManyField("spider.Protection", through="spider.AssignedProtection")
    class Meta:
        abstract = True
        unique_together = [("user", "name"),]
        indexes = [
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self):
        return self.name

    def validate(self, request):
        # with deny and protections
        if self.assigned.filter(code="deny", active=True).exists() and len(self.assigned) > 1:
            for p in self.assigned.filter(active=True).exclude(code="deny"):
                if not p.validate(request):
                    return False
            for rec, error in validate_success.send_robust(sender=self.__class__, name=self.name, code="deny"):
                logger.error(error)
            return True
        else:
            # normally just one must be fullfilled (or)
            for p in self.assigned.filter(active=True):
                if p.validate(request):
                    for rec, error in validate_success.send_robust(sender=self.__class__, name=self.name, code=p.code):
                        logger.error(error)
                    return True
            return False

    def get_absolute_url(self):
        return reverse("spiderpk:uc-view", kwargs={"user":self.user.username, "name":self.name})


class UserComponent(AbstractUserComponent):
    class Meta:
        swappable = swapper.swappable_setting('spider', 'UserComponent')


from .protections import Protection, AssignedProtection
