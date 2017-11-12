from django.contrib import admin

import swapper
Broker = swapper.load_model("spiderbrokers", "Broker")

# Register your models here.

@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    fields = ['extra', 'protected_by']
