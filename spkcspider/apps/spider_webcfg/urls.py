from django.urls import path


from .views import WebConfigForm

app_name = "spider_webcfg"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        '',
        WebConfigForm.as_view(),
        name='webconfig-form'
    )
]
