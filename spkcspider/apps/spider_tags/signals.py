
def UpdateDefaultLayouts(sender, **kwargs):
    # provided apps argument lacks model function support
    # so use this
    from django.apps import apps
    from .layouts import initialize_layouts
    initialize_layouts(apps)
