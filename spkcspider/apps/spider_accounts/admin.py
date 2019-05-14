from django.contrib import admin
from django.contrib.auth import admin as user_admin
from django.utils.translation import gettext_lazy as _

from .models import SpiderUser
# Register your models here.


@admin.register(SpiderUser)
class UserAdmin(user_admin.UserAdmin):
    # exclude = ["first_name", "last_name"]
    list_display = ('username', 'email', 'is_active', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('email',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff',
                                       'is_superuser',
                                       'quota_local', 'quota_remote',
                                       'quota_usercomponents', 'groups',
                                       'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    def has_module_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        if obj:
            if not request.user.is_active:
                return False
            if request.user.is_superuser or request.user == obj:
                return True
            # only superuser can alter superusers
            if obj.is_superuser:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if obj and obj != request.user:
            if request.user.is_superuser:
                return True
            # only superuser can delete superusers
            if obj.is_superuser:
                return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = []
        if not request.user.is_superuser:
            fields.append("is_superuser")
            fields.append("last_login")
            fields.append("date_joined")
            if not self.has_change_permission(request, obj):
                fields.append("groups")
                fields.append("permissions")
                fields.append("is_staff")
        return fields
