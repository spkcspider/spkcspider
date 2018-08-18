from spkcspider.apps.spider.models import UserInfo


def SetupUserCallback(sender, instance, **kwargs):
    if kwargs.get("created", False):
        return
    if kwargs.get("raw", False):
        return
    if not hasattr(instance, "spider_info"):
        instance.spider_info = UserInfo.objects.create(
            user=instance
        )
