from django.contrib.auth.models import Permission


def InitialGrantsCallback(sender, instance, **kwargs):
    if kwargs.get("created", False):
        return
    if kwargs.get("raw", False):
        return
    for t in ["add_usercomponent", "add_usercontent"]:
        model = Permission.objects.get(codename=t)
        instance.user_permissions.add(model)
