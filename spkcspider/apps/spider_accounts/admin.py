from django.contrib import admin
from django.contrib.auth import admin as user_admin

from .models import SpiderUser
# Register your models here.


@admin.register(SpiderUser)
class UserAdmin(user_admin.UserAdmin):

    def has_change_permission(self, request, obj=None):
        if obj and obj != request.user:
            if request.user.is_superuser:
                return True
            # only superuser can alter superusers
            if obj.is_superuser:
                return False
        super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj != request.user:
            if request.user.is_superuser:
                return True
            # only superuser can delete superusers
            if obj.is_superuser:
                return False
        super().has_delete_permission(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            form.fields["is_superuser"].disabled = True
        return form
