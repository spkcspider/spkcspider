from django.contrib import admin

from .models import Protection, AssignedProtection, UserComponent, UserContent

# Register your models here.

class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['protectiondata', 'active', 'protection']

class UserContentInline(admin.TabularInline):
    model = UserContent
    fields = ['info', 'deletion_requested']
    # content is not visible


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        UserContentInline,
        AssignedProtectionInline,
    ]
    fields = ['name']

    def has_delete_permission(self, request, obj=None):
        if obj and obj.name in ["index", "recovery"]:
            return False
        return super().has_delete_permission(request, obj)

@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    fields = ['code']
