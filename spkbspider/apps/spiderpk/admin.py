from django.contrib import admin

import swapper
UserComponent = swapper.load_model("spiderpk", "UserComponent")
PublicKey = swapper.load_model("spiderpk", "PublicKey")

# Register your models here.
@admin.register(UserComponent)
class UserComponentAdmin(admin.ModelAdmin):
    pass

@admin.register(PublicKey)
class PublicKeyAdmin(admin.ModelAdmin):
    pass
