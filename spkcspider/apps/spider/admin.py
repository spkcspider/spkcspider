from django.contrib import admin
from django.conf import settings

from .models import (
    Protection, AssignedProtection, UserComponent, AssignedContent,
    ContentVariant, UserInfo
)


@admin.register(AssignedContent)
class AssignedContentAdmin(admin.ModelAdmin):
    fields = ['info', 'created', 'modified', 'deletion_requested', 'token']
    readonly_fields = [
        'info', 'created', 'modified'
    ]

    def has_module_permission(self, request):
        return True

    def has_delete_permission(self, request, obj=None):
        n = request.user._meta.app_label
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj or request.user.is_superuser:
            return True
        # obj is UserComponent
        if obj.usercomponent.name == "index":
            return request.user.has_perm("{}.delete_{}".format(n, m))
        return request.user.has_perm("spider_base.delete_assignedcontent")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        # obj is UserComponent
        if not obj or obj.usercomponent.name == "index":
            return False
        return request.user.has_perm("spider_base.view_assignedcontent")

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        # obj is UserComponent
        if not obj or obj.usercomponent.name == "index":
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("spider_base.change_assignedcontent")

    def has_add_permission(self, request, obj=None):
        return False


class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    # protection field is not possible (and shouldn't, can corrupt data)
    # data is too dangerous, admin should not have access to e.g. pws
    fields = [
        'created', 'modified', 'active', 'instant_fail'
    ]
    readonly_fields = ['created', 'modified']
    fk_name = 'usercomponent'
    extra = 0

    def has_add_permission(self, request, obj=None):
        # adding protection doesn't make sense without data
        return False


class ContentInline(admin.TabularInline):
    model = AssignedContent
    fields = [
        'info', 'created', 'modified', 'deletion_requested', 'token'
    ]
    readonly_fields = [
        'info', 'created', 'modified'
    ]
    # until fixed:
    readonly_fields += ['deletion_requested', 'token']
    show_change_link = True
    extra = 0
    # content is not visible

    def has_delete_permission(self, request, obj=None):
        n = request.user._meta.app_label
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj or request.user.is_superuser:
            return True
        # obj is UserComponent
        if obj.name == "index":
            return request.user.has_perm("{}.delete_{}".format(n, m))
        return request.user.has_perm("spider_base.delete_usercontent")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        # obj is UserComponent
        if not obj or obj.name == "index":
            return False
        return request.user.has_perm("spider_base.view_usercontent")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        ContentInline,
        AssignedProtectionInline,
    ]
    actions = ["feature", "unfeature"]
    fields = [
        'user', 'name', 'created', 'modified', 'description', 'features',
        'can_auth', 'allow_domain_mode',
        'featured', 'public', 'strength', 'token', 'required_passes',
        'deletion_requested', 'token_duration'
    ]
    readonly_fields = [
        'created', 'modified', 'featured', 'strength',
        'can_auth', 'allow_domain_mode'
    ]
    list_display = ('name', 'username', 'strength', 'featured', 'modified')
    view_on_site = True

    def has_module_permission(self, request):
        return True

    def feature(self, request, queryset):
        queryset.exclude(
            name__in=("index", "fake_index")
        ).exclude(public=False).update(featured=True)
    feature.allowed_permissions = ('can_feature',)

    def unfeature(self, request, queryset):
        queryset.update(featured=False)
    unfeature.allowed_permissions = ('can_feature',)

    def has_can_feature_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("spider_base.can_feature")

    def has_add_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_perm("spider_base.add_usercomponent")

    def has_delete_permission(self, request, obj=None):
        n = request.user._meta.app_label
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        # you must be able to delete user to delete index component
        if obj and obj.name == "index":
            if not request.user.has_perm("{}.delete_{}".format(n, m)):
                return False
        return request.user.has_perm("spider_base.delete_usercomponent")

    def has_view_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        if obj and obj.name == "index" and obj.user != request.user:
            return False
        return request.user.has_perm("spider_base.view_usercomponent")

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        if obj and obj.name == "index" and obj.user != request.user:
            return False
        return request.user.has_perm("spider_base.change_usercomponent")


@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    view_on_site = False
    fields = ['code']

    def has_module_permission(self, request):
        return True

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
    view_on_site = False
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
        n = request.user._meta.app_label
        m = request.user._meta.model_name
        if not request.user.is_active:
            return False
        # not obj allows deletion of users
        if not obj:
            return True
        return request.user.has_perm("{}.delete_{}".format(n, m))


if 'django.contrib.flatpages' in settings.INSTALLED_APPS:
    from django.contrib.flatpages.admin import FlatPageAdmin
    from .forms.flatpages import FlatpageItemForm

    FlatPageAdmin.form = FlatpageItemForm
