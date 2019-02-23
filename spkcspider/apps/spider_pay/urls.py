from django.urls import path


from .views import PaymentsListView

app_name = "spider_pay"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        '',
        PaymentsListView.as_view(),
        name='payments-list'
    )
]
