from django.urls import path


from .views import WebConfigView

app_name = "spider_pay"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        '',
        WebConfigView.as_view(),
        name='webconfig-view'
    )
]
