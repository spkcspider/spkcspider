
from django.conf import settings
from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView

from .views import (
    LoginView, LogoutView, PasswordChangeDoneView, PasswordChangeView,
    SignupDoneView, SignupView, UpdateView
)

app_name = "auth"

# no recovery, only authentication

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path(
        'password_change/',
        PasswordChangeView.as_view(
            success_url=reverse_lazy("auth:password_change_done")
        ), name='password_change'
    ),
    path(
        'password_change/done/',
        PasswordChangeDoneView.as_view(), name='password_change_done'
    ),
    path('profile/', UpdateView.as_view(), name="profile"),
    path(
        '',
        RedirectView.as_view(
            url=reverse_lazy('auth:profile'),
            permanent=True
        )
    ),
]
if getattr(settings, "OPEN_FOR_REGISTRATION", False):
    urlpatterns.append(
        path('signup/', SignupView.as_view(), name="signup")
    )
    urlpatterns.append(
        path(
            'thanks/',
            SignupDoneView.as_view(), name="signup_done"
        )
    )
