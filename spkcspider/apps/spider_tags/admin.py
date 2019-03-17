from django.contrib import admin

# Register your models here.

from .models import (
    TagLayout
)


@admin.register(TagLayout)
class AssignedContentAdmin(admin.ModelAdmin):
    fields = ['name', 'unique', 'layout', 'default_verifiers', 'usertag']
