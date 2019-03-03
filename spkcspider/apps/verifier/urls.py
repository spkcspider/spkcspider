from django.urls import path


from .views import CreateEntry, VerifyEntry, HashAlgoView


app_name = "spider_verifier"

urlpatterns = [
    path(
        'task/<slug:task_id>/',
        CreateEntry.as_view(),
        name='task'
    ),
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
    # NOTE: this view is csrf_exempted
    path(
        '',
        CreateEntry.as_view(),
        name='create'
    ),

]
