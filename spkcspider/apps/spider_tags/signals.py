__all__ = ["UpdateLayouts"]

from . import registry


def UpdateLayouts(sender, **kwargs):
    registry.layouts.initialize()
