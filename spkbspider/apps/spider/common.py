
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.shortcuts import get_object_or_404


class ObjectTestMixin(UserPassesTestMixin):
    object = None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.request.user == self.object.user:
            return True
        return False

    def get_user(self):
        return get_user_model().objects.filter(username=self.kwargs["user"]).first()

    def test_user_has_special_permissions(self, obuser):
        if not self.request.user.is_active or not self.request.user.is_authenticated:
            return False
        if self.request.user == obuser:
            return True
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        return False

    def test_use_uc(self, ucname, obuser):
        if hasattr(self, "object"):
            if self.object.protected_by:
                return self.object.protected_by.auth_test(self.request)
        uc = self.model.objects.get_or_create(name=ucname, user=obuser)
        return uc.test(self.request)

    def handle_no_permission(self):

        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())


class UserListView(UserPassesTestMixin, ListView):
    def test_func(self):
        # 404 if user does not exist
        obuser = get_object_or_404(self.get_user())
        #if not obuser:
        #    #nothing to see
        #    return True
        if self.test_user_has_special_permissions(obuser):
            return True
        if self.test_use_uc("publickeys", obuser):
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(user__username=self.kwargs["user"])

class UserDetailView(UserPassesTestMixin, DetailView):
    def test_func(self):
        obuser = self.get_user()
        if not obuser:
            #nothing to see
            return True
        if self.test_user_has_special_permissions(obuser):
            return True
        if self.test_use_uc("publickeys", obuser):
            return True
        return False

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user__username=self.kwargs["user"], hash=self.kwargs["hash"])
        else:
            return get_object_or_404(self.get_queryset(), user__username=self.kwargs["user"], hash=self.kwargs["hash"])
