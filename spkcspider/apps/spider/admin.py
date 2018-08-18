from django.contrib import admin

from .models import (
    Protection, AssignedProtection, UserComponent, AssignedContent,
    ContentVariant
)

# Register your models here.


class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['active', 'instant_fail', 'protection']

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        if not obj:
            return False
        return request.user == obj.usercomponent.user

    def has_view_permission(self, request, obj=None):
        if not obj:
            return True
        return request.user.is_superuser or \
            request.user.is_staff or \
            request.user == obj.usercomponent.user

    has_delete_permission = has_view_permission
    has_change_permission = has_view_permission


class UserContentInline(admin.TabularInline):
    model = AssignedContent
    fields = ['info', 'deletion_requested', 'nonce']
    # content is not visible

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not obj or obj.usercomponent.name == "index":
            return False
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or request.user == obj.user:
            return True
        if not obj or obj.usercomponent.name == "index":
            return False
        return request.user.has_perm("spider_base.view_usercontent")

    def has_change_permission(self, request, obj=None):
        if not obj:
            return False
        if obj.usercomponent.name == "index":
            return False
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        if not obj:
            return False
        return request.user.has_perm("spider_base.add_usercontent")


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        UserContentInline,
        AssignedProtectionInline,
    ]
    fields = ['name', 'deletion_requested', 'nonce']

    def has_delete_permission(self, request, obj=None):
        if not obj and request.user.is_superuser:
            return True
        if not obj or obj.name == "index":
            return False
        return request.user.has_perm("spider_base.delete_usercomponent")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not obj or obj.name == "index":
            return False
        return request.user == obj.user or request.user.is_staff

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or \
           request.user.has_perm("spider_base.change_usercomponent"):
            return True
        return request.user == obj.user

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        return request.user.has_perm("spider_base.add_usercomponent")


@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    fields = ['code']

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.is_staff

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.is_staff


@admin.register(ContentVariant)
class ContentVariantAdmin(ProtectionAdmin):
    fields = ['name']
