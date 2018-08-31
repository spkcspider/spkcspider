from django.contrib import admin
from django.contrib.auth import admin as user_admin

from .models import SpiderUser
# Register your models here.


@admin.register(SpiderUser)
class UserAdmin(user_admin.UserAdmin):
    pass
