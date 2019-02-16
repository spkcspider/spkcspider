from django.urls import path


from .views import PushTagView

app_name = "spider_tags"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        '',
        PushTagView.as_view(),
        name='create-pushtag'
    )
]
