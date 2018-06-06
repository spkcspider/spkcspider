from django.urls import path, reverse_lazy

from .views import SignupView, UserUpdateView, UserLoginView
from django.contrib.auth.views import (
    LogoutView, PasswordChangeView, PasswordChangeDoneView
)
from django.views.generic.base import RedirectView, TemplateView

app_name = "spideraccounts"

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
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
    # forget recovery, only authentication
    path('signup/', SignupView.as_view(), name="signup"),
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
