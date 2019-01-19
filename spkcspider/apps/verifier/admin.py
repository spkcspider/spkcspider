

from django.utils.timezone import now

from django.contrib import admin
from django.contrib.auth import get_permission_codename

from .models import DataVerificationTag

# Register your models here.


@admin.register(DataVerificationTag)
class DataVerificationTagAdmin(admin.ModelAdmin):
    view_on_site = True
    list_display = ('hash', "checked", 'verification_state')
    search_fields = ('hash', "checked", 'verification_state')
    fields = [
        'created', 'modified', "checked", 'dvfile', 'verification_state',
        'note'
    ]
    readonly_fields = ['created', 'modified', "checked"]

    def get_form(self, request, obj=None, **kwargs):
        ret = super().get_form(request, obj, **kwargs)
        opts = self.opts
        codename = get_permission_codename('change', opts)
        if not request.user.has_perm("%s.%s" % (opts.app_label, codename)):
            ret.fields["dvfile"].disabled = True
        return ret

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        codename = get_permission_codename('can_verify', opts)
        if request.user.has_perm("%s.%s" % (opts.app_label, codename)):
            return True
        codename = get_permission_codename('change', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def save_form(self, request, form, change):
        if 'verification_state' in form.changed_data:
            form.instance.checked = now()
        return super().save_form(request, form, change)

    def save_model(self, request, obj, form, change):
        """
        Given a model instance save it to the database.
        """
        if 'verification_state' in form.changed_data:
            obj.checked = now()
        return super().save_model(request, obj, form, change)
