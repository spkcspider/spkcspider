from django.urls import path
from django.views.decorators.csrf import csrf_exempt


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
        csrf_exempt(CreateEntry.as_view()),
        name='create'
    ),

]
