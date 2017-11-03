
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

import swapper

UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")
Broker = swapper.load_model("spiderbroker", "Broker")

@receiver(post_save, sender=get_user_model(), dispatch_uid="initial_grants_user")
def InitialGrantsCallback(sender, instance, **kwargs):
    for model in [UserComponent, PublicKey, Broker]:
        user.user_permissions.add('{}.{}_add'.format(model._meta.app_label, model._meta.model_name))
