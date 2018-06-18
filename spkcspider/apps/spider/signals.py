__all__ = (
    "UpdateProtectionsCallback", "InitUserComponentsCallback",
    "UpdateContentsCallback"
)
from django.dispatch import Signal

test_success = Signal(providing_args=["name", "code"])


def UpdateContentsCallback(sender, plan=None, **kwargs):
    # provided apps argument lacks model function support
    # so use this
    from django.apps import apps
    from .contents import initialize_content_models
    initialize_content_models(apps)

    # regenerate info (migrate with >0 migrations)
    if not plan or len(plan) == 0:
        return

    UserContent = apps.get_model("spider_base", "UserContent")
    for row in UserContent.objects.all():
        # works only with django.apps.apps
        row.info = row.content.get_info(row.usercomponent)
        row.save(update_fields=['info'])


def UpdateProtectionsCallback(sender, **kwargs):
    # provided apps argument lacks model function support
    # so use global apps
    from .protections import initialize_protection_models
    initialize_protection_models()


def InitUserComponentsCallback(sender, instance, **kwargs):
    from .models import UserComponent, Protection, AssignedProtection
    uc = UserComponent.objects.get_or_create(name="index", user=instance)[0]
    login = Protection.objects.filter(code="login").first()
    if login:
        asuc = AssignedProtection.objects.get_or_create(
            defaults={"active": True},
            usercomponent=uc, protection=login
        )[0]
        if not asuc.active:
            asuc.active = True
            asuc.save()
