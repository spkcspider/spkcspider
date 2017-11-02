from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, LoginView
from django.views.generic.edit import FormView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.contrib.auth import get_user_model

import time
from .forms import SignupForm, UserUpdateForm

# Create your views here.

class SignupView(FormView):
    template_name = 'registration/signup.html'
    form_class = SignupForm
    success_url = reverse_lazy("auth:signup_thanks")

    def post(self, request, *args, **kwargs):
        # slow down signups, helpfull against bots
        time.sleep(3)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        username = form.cleaned_data.get('username')
        raw_password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=raw_password)
        login(self.request, user)
        return HttpResponseRedirect(self.get_success_url())

class UserLoginView(LoginView):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)
    def post(self, request, *args, **kwargs):
        # slow down login attempts, helpfull against bruteforce attacks
        time.sleep(1.5)
        return super().post(request, *args, **kwargs)

class UserUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'registration/profile.html'
    form_class = UserUpdateForm
    def get_object(self, queryset=None):
        obj = get_user_model().objects.get(id=self.request.user.pk)
        return obj

class RecoverView(PasswordResetView):
    success_url = reverse_lazy('auth:password_reset_confirm')
    def post(self, request, *args, **kwargs):
        # slow down recover requests, helpfull against bots
        time.sleep(3)
        return super().post(request, *args, **kwargs)

class ResetView(PasswordResetConfirmView):
    success_url = reverse_lazy('auth:password_reset_complete')
