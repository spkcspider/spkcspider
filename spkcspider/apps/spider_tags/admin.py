from django.contrib import admin

from .forms import TagLayoutAdminForm
from .models import TagLayout

# Register your models here.



@admin.register(TagLayout)
class TagLayoutAdmin(admin.ModelAdmin):
    form = TagLayoutAdminForm
