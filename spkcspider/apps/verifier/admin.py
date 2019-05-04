
import logging
from django.utils.timezone import now

from django.contrib import admin
from django.contrib.auth import get_permission_codename

from .models import DataVerificationTag

logger = logging.getLogger(__name__)


@admin.register(DataVerificationTag)
class DataVerificationTagAdmin(admin.ModelAdmin):
    view_on_site = True
    list_display = ('hash', "checked", 'verification_state')
    search_fields = ('hash', "checked", 'verification_state')
    fields = [
        'created', 'modified', 'checked', 'dvfile', 'verification_state',
        'note'
    ]
    readonly_fields = ['created', 'modified', "checked"]

    def get_form(self, request, obj=None, **kwargs):
        opts = self.opts
        codename = get_permission_codename('change', opts)
        if not request.user.has_perm("%s.%s" % (opts.app_label, codename)):
            self.readonly_fields = [
                'created', 'modified', 'checked', 'dvfile'
            ]
        return super().get_form(request, obj, **kwargs)

    def has_module_permission(self, request):
        return True

    def has_view_permission(self, request, obj=None):
        opts = self.opts
        if request.user.has_perm("%s.%s" % (opts.app_label, 'can_verify')):
            return True
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        if request.user.has_perm("%s.%s" % (opts.app_label, 'can_verify')):
            return True
        return super().has_change_permission(request, obj)

    def save_form(self, request, form, change):
        if 'verification_state' in form.changed_data:
            form.instance.checked = now()
        ret = super().save_form(request, form, change)
        try:
            form.instance.callback(
                "{}://{}".format(
                    request.scheme, request.get_host()
                )
            )
        except Exception as exc:
            logger.exception("Callback failed", exc_info=exc)
        return ret

    # def save_model(self, request, obj, form, change):
    #    """
    #    Given a model instance save it to the database.
    #    """
    #    if 'verification_state' in form.changed_data:
    #        obj.checked = now()
    #    ret = super().save_model(request, obj, form, change)
    #    obj.callback()
    #    return ret
