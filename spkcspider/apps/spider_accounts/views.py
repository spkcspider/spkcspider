__all__ = (
    "SignupView", "UserLoginView", "UserLogoutView", "UserUpdateView"
)

from django.http import HttpResponseRedirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic.edit import FormView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.conf import settings

from .forms import SignupForm, UserUpdateForm
from spkcspider.apps.spider.forms import SpiderAuthForm

# Create your views here.


class SignupView(FormView):
    template_name = 'registration/signup.html'
    form_class = SignupForm
    success_url = reverse_lazy("auth:signup_thanks")

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


class UserLoginView(LoginView):
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


class UserLogoutView(LogoutView):
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        ret = super().dispatch(request, *args, **kwargs)
        ret["Clear-Site-Data"] = "*"
        return ret


class UserUpdateView(LoginRequiredMixin, UpdateView):
    success_url = reverse_lazy('auth:profile')
    template_name = 'registration/profile.html'
    form_class = UserUpdateForm

    def get_object(self, queryset=None):
        obj = get_user_model().objects.get(id=self.request.user.pk)
        return obj
