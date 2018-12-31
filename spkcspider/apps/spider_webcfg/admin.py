
from django.contrib import admin

from .models import WebConfig


@admin.register(WebConfig)
class WebConfigAdmin(admin.ModelAdmin):
    fields = ['url']
    readonly_fields = []
