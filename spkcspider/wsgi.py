"""
WSGI config for spkcspider project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spkcspider.settings.debug")
if not os.environ.get(
    "SPIDER_SILENCE",
    "django.core.management" in sys.modules  # is loaded by manage.py
):
    print("USE SETTINGS:", os.environ["DJANGO_SETTINGS_MODULE"])

application = get_wsgi_application()
