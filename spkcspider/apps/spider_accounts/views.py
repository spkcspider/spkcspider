__all__ = (
    "SignupView", "LoginView", "LogoutView", "UpdateView",
    "PasswordChangeView", "PasswordChangeDoneView", "SignupDoneView"
)

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as _LoginView
from django.contrib.auth.views import LogoutView as _LogoutView
from django.contrib.auth.views import \
    PasswordChangeDoneView as _PasswordChangeDoneView
from django.contrib.auth.views import PasswordChangeView as _PasswordChangeView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView, UpdateView
from spkcspider.apps.spider.forms import SpiderAuthForm
from spkcspider.apps.spider.views import DefinitionsMixin

from .forms import SignupForm, UserUpdateForm

# Create your views here.


class PasswordChangeView(DefinitionsMixin, _PasswordChangeView):
    pass


class PasswordChangeDoneView(DefinitionsMixin, _PasswordChangeDoneView):
    pass


class SignupView(DefinitionsMixin, FormView):
    template_name = 'registration/signup.html'
    form_class = SignupForm
    success_url = reverse_lazy("auth:signup_done")

    def form_valid(self, form):
        form.save()
        username = form.cleaned_data.get('username')
        raw_password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=raw_password)
        login(self.request, user)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        if "next" in self.request.GET:
            return self.request.GET["next"]
        return self.success_url


class SignupDoneView(DefinitionsMixin, TemplateView):
    template_name = 'registration/thanks.html'


class LoginView(DefinitionsMixin, _LoginView):
    form_class = SpiderAuthForm

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Security check complete. Log the user in."""
        # backend for loging in, select the first
        backend = settings.AUTHENTICATION_BACKENDS[0]
        login(
            self.request,
            form.get_user(),
            backend
        )
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        form.reset_protections()
        return super().form_invalid(form)


class LogoutView(DefinitionsMixin, _LogoutView):
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        ret = super().dispatch(request, *args, **kwargs)
        ret["Clear-Site-Data"] = "*"
        return ret


class UpdateView(DefinitionsMixin, LoginRequiredMixin, UpdateView):
    success_url = reverse_lazy('auth:profile')
    template_name = 'registration/profile.html'
    form_class = UserUpdateForm

    def get_object(self, queryset=None):
        # clone user object
        return get_user_model().objects.get(pk=self.request.user.pk)
