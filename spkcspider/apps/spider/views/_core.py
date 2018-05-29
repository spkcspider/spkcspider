__all__ = ("UserTestMixin", "UCTestMixin")

from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http.response import HttpResponseBase

from ..contents import UserContentType
from ..protections import ProtectionType
from ..models import UserComponent


class UserTestMixin(UserPassesTestMixin):
    results_tests = None

    def get_context_data(self, **kwargs):
        kwargs["UserContentType"] = UserContentType
        kwargs["ProtectionType"] = ProtectionType
        return super().get_context_data(**kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

    def has_special_access(self, staff=False, superuser=True):
        if self.request.user == self.get_user():
            return True
        if superuser and self.request.user.is_superuser:
            return True
        if staff and self.request.user.is_staff:
            return True
        return False

    def get_user(self):
        username = None
        if "user" in self.kwargs:
            username = self.kwargs["user"]
        elif self.request.user.is_authenticated:
            username = self.request.user.username
        return get_object_or_404(get_user_model(), username=username)

    def get_usercomponent(self):
        return get_object_or_404(
            UserComponent, user=self.get_user(), name=self.kwargs["name"]
        )

    def handle_no_permission(self):
        if not bool(self.results_tests):
            return super().handle_no_permission()
        if len(self.results_tests) == 1:
            if isinstance(self.results_tests[0].result, HttpResponseBase):
                return self.results_tests[0].result
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=self.get_context_data(protections=self.results_tests),
            using=self.template_engine,
            content_type=self.content_type
        )

    def get_noperm_template_names(self):
        return "spiderprotections/protections.html"


class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)
