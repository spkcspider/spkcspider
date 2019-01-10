__all__ = ("DeleteAssociatedWebCfg", )


def DeleteAssociatedWebCfg(sender, instance, remote, **kwargs):
    from .models import WebConfig
    WebConfig.objects.filter(
        usercomponent=instance,
        url=remote
    ).delete()
