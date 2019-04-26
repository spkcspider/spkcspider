__all__ = [
    "PWOpenChoiceWidget",
]

from ._base import OpenChoiceWidget


class PWOpenChoiceWidget(OpenChoiceWidget):
    anchor_class = "PWProtectionTarget"

    class Media:
        overwrite = True
