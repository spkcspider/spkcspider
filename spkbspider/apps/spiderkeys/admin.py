from django.contrib import admin

import swapper
PublicKey = swapper.load_model("spiderkeys", "PublicKey")

# Register your models here.

@admin.register(PublicKey)
class PublicKeyAdmin(admin.ModelAdmin):
    fields = ['key', 'note', 'hash', 'protected_by']
