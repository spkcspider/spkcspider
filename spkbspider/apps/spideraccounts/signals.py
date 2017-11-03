from django.contrib.auth.models import Permission

import swapper

UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")
Broker = swapper.load_model("spiderbroker", "Broker")

def InitialGrantsCallback(sender, instance, **kwargs):
    for t in [UserComponent, PublicKey, Broker]:
        model = Permission.objects.get(codename='add_{}'.format(t._meta.model_name))
        instance.user_permissions.add(model)
