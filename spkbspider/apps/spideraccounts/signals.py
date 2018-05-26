from django.contrib.auth.models import Permission


def InitialGrantsCallback(sender, instance, **kwargs):
    for t in ["add_usercomponent", "add_usercontent"]:
        model = Permission.objects.get(codename=t)
        instance.user_permissions.add(model)
    instance.save()
