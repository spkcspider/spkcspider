from django.contrib import admin

from .protections import Protection, AssignedProtection
import swapper
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")

# Register your models here.

@admin.register(PublicKey)
class PublicKeyAdmin(admin.ModelAdmin):
    fields = ['key', 'note', 'hash', 'protected_by']


class AssignedProtectionInline(admin.TabularInline):
    model = AssignedProtection
    fields = ['protectiondata', 'active', 'protection']


@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    inlines = [
        AssignedProtectionInline,
    ]
    fields = ['brokers', 'publickeys', 'name', 'data']

@admin.register(Protection)
class ProtectionAdmin(admin.ModelAdmin):
    pass
