from django.contrib.auth.models import Permission


from spkbspider.apps.spider.models import UserComponent, UserContent

def InitialGrantsCallback(sender, instance, **kwargs):
    for t in [UserComponent, UserContent]:
        model = Permission.objects.get(codename='add_{}'.format(t._meta.model_name))
        instance.user_permissions.add(model)
