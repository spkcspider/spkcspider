from django.dispatch import Signal

validate_success = Signal(providing_args=["name", "code"])
