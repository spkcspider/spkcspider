from django.urls import path

from .views import CreateEntry, VerifyEntry


app_name = "spider_verifier"

urlpatterns = [
    path(
        '<slug:hash>/',
        VerifyEntry.as_view(),
        name='verify'
    ),
    path(
        '',
        CreateEntry.as_view(),
        name='create'
    ),

]
