from django.contrib import admin

# Register your models here.

from .models import (
    TagLayout
)
from .forms import TagLayoutAdminForm


@admin.register(TagLayout)
class TagLayoutAdmin(admin.ModelAdmin):
    form = TagLayoutAdminForm
