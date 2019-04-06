__all__ = ("content_name_validator",)


from django.core.exceptions import ValidationError

from django.utils.translation import gettext_lazy as _


def content_name_validator(value):
    if not value.isprintable():
        raise ValidationError(
            _("Contains control characters"),
            code="control_characters"
        )
    if value:
        if value[0].isspace() or value[1].isspace():
            raise ValidationError(
                _("Contains hidden spaces"),
                code="hidden_spaces"
            )
