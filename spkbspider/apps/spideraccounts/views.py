from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy

from .forms import SignupForm, UserUpdateForm

# Create your views here.

class SignupView(FormView):
    template_name = 'registration/signup.html'
    form_class = SignupForm
    success_url = '/thanks/'

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        form.save()
        username = form.cleaned_data.get('username')
        raw_password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=raw_password)
        login(self.request, user)
        return HttpResponseRedirect(self.get_success_url())


class UserUpdateView(LoginRequiredMixin, FormView):
    template_name = 'registration/account.html'
    form_class = UserUpdateForm


class RecoverView(PasswordResetView):
    success_url = reverse_lazy('auth:password_reset_confirm')

class ResetView(PasswordResetConfirmView):
    success_url = reverse_lazy('auth:password_reset_complete')
