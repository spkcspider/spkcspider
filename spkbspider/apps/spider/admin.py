from django.contrib import admin

from .models import Protection, AssignedProtection
import swapper
UserComponent = swapper.load_model("spiderucs", "UserComponent")

# Register your models here.

class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['protectiondata', 'active', 'protection']


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        AssignedProtectionInline,
    ]
    fields = ['contents', 'name']

@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    fields = ['code']
