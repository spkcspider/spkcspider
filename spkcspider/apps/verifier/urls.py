from django.urls import path


from .views import CreateEntry, TaskView, VerifyEntry, HashAlgoView


app_name = "spider_verifier"

urlpatterns = [
    path(
        'task/<int:pk>/',
        TaskView.as_view(),
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
