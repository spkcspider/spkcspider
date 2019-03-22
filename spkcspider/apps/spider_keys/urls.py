from django.urls import path


from .views import PermAnchorView

app_name = "spider_keys"


urlpatterns = [
    path(
        'anchor/<int:pk>/view/',
        PermAnchorView.as_view(),
        name='anchor-permanent'
    )
]
