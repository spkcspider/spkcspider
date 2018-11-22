
from django.conf import settings
from django.urls import path, reverse_lazy

from django.contrib.auth.views import (
    PasswordChangeView, PasswordChangeDoneView
)
from django.views.generic.base import RedirectView, TemplateView

from .views import SignupView, UserUpdateView, UserLoginView, UserLogoutView


app_name = "auth"

# no recovery, only authentication

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
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
    path(
        'thanks/',
        TemplateView.as_view(template_name='registration/thanks.html'),
        name="signup_thanks"
    ),
    path('profile/', UserUpdateView.as_view(), name="profile"),
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
