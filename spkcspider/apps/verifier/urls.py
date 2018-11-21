from django.urls import path
from django.views.decorators.csrf import csrf_exempt


from .views import CreateEntry, VerifyEntry, HashAlgoView


app_name = "spider_verifier"

urlpatterns = [
    path(
        'hash/<slug:hash>/',
        VerifyEntry.as_view(),
        name='verify'
    ),
    path(
        'hash/',
        HashAlgoView.as_view(),
        name='hash_algo'
    ),
    path(
        '',
        csrf_exempt(CreateEntry.as_view()),
        name='create'
    ),

]
