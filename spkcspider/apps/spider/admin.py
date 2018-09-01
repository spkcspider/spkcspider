from django.contrib import admin

from .models import (
    Protection, AssignedProtection, UserComponent, AssignedContent,
    ContentVariant, UserInfo
)

# Register your models here.


class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['active', 'instant_fail', 'protection']

    def has_add_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if obj and request.user == obj.user:
            return True
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if obj and request.user == obj.user:
            return True
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and request.user == obj.user:
            return True

        if not request.user.is_active:
            return False
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if not obj:
            return True
        return request.user.is_superuser or \
            request.user.is_staff or \
            request.user == obj.user


class UserContentInline(admin.TabularInline):
    model = AssignedContent
    fields = ['info', 'deletion_requested', 'nonce']
    # content is not visible

    def has_delete_permission(self, request, obj=None):
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj or request.user.is_superuser:
            return True
        # obj is UserComponent
        if obj.name == "index":
            return request.user.has_perm("spider_base.delete_{}".format(m))
        return request.user.has_perm("spider_base.delete_usercontent")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        # obj is UserComponent
        if not obj or obj.name == "index":
            return False
        return request.user.has_perm("spider_base.view_usercontent")

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        # obj is UserComponent
        if not obj or obj.name == "index":
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("spider_base.change_usercontent")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        UserContentInline,
        AssignedProtectionInline,
    ]
    fields = ['name', 'deletion_requested', 'nonce']

    def has_add_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("spider_base.add_usercomponent")

    def has_delete_permission(self, request, obj=None):
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of user
        if not obj or request.user.is_superuser:
            return True
        if obj.name == "index":
            return request.user.has_perm("spider_base.delete_{}".format(m))
        return request.user.has_perm("spider_base.delete_usercomponent")

    def has_view_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        if not obj or obj.name == "index":
            return False
        return request.user == obj.user or request.user.is_staff

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser or \
           request.user.has_perm("spider_base.change_usercomponent"):
            return True
        return request.user == obj.user


@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    fields = ['code']

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        return request.user.is_superuser or request.user.is_staff

    def has_add_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        return request.user.is_superuser or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        return request.user.is_superuser or request.user.is_staff


@admin.register(ContentVariant)
class ContentVariantAdmin(ProtectionAdmin):
    fields = ['name']


@admin.register(UserInfo)
class UserInfoAdmin(admin.ModelAdmin):
    fields = []

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_view_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        return request.user.is_superuser or request.user.is_staff

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj:
            return True
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj:
            return True
        return request.user.has_perm("spider_base.delete_{}".format(m))
