from django.contrib import admin

from .models import Protection, AssignedProtection, UserComponent, UserContent

# Register your models here.

class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['protectiondata', 'active', 'protection']

class UserContentInline(admin.TabularInline):
    model = UserContent
    fields = ['info', 'deletion_requested']


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        UserContentInline,
        AssignedProtectionInline,
    ]
    fields = ['name']

@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    fields = ['code']
