from django.urls import path


from .views import WebReferenceView

app_name = "spider_webref"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        '',
        WebReferenceView.as_view(),
        name='webref-view'
    )
]
