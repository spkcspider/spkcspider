
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .models import UserComponent

class ObjectTestMixin(UserPassesTestMixin):
    object = None
    protection = None
    noperm_template_name = "spiderucs/protection_list.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.request.user == self.object.associated.usercomponent.user:
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

    def use_uc(self, obuser, ucname=None):
        if hasattr(self, "object"):
            if self.object.associated:
                self.uc = self.object.associated.usercomponent
        else:
            self.uc = UserComponent.objects.get(name=ucname, user=obuser)
        if "protection" in request.GET:
            self.protection = get_object_or_404(AssignedProtection, usercomponent=self.uc, protection__name=request.GET["protection"])
            if self.request.method == "GET":
                # skip testing because no values exist
                return False
            else:
                return self.protection.auth_test(self.request)
        else:
            return self.uc.auth_test_pre(self.request)

    def get_noperm_template_names(self):
        return [self.noperm_template_name]

    def handle_no_permission(self):
        if self.protection:
            return self.protection.auth_render(self.request)
        if not self.uc:
            raise PermissionDenied(self.get_permission_denied_message())
        auth_methods = self.uc.list_protections(self.request)
        if len(auth_methods) == 0:
            raise PermissionDenied(self.get_permission_denied_message())
        context = {"object_list": auth_methods}
        return TemplateResponse(
            request=self.request,
            template=self.get_noperm_template_names(),
            context=context,
            using=self.template_engine,
            content_type=getattr(self, "content_type",None)
        )
        #return redirect_to_login(self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())


class UserListView(UserPassesTestMixin, ListView):
    uc_name = None
    def test_func(self):
        # 404 if user does not exist
        obuser = get_object_or_404(self.get_user())
        #if not obuser:
        #    #nothing to see
        #    return True
        if self.test_user_has_special_permissions(obuser):
            return True
        if self.use_uc(obuser, uc_name):
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(user__username=self.kwargs["user"])

class UserDetailView(UserPassesTestMixin, DetailView):
    uc_name = None
    def test_func(self):
        obuser = self.get_user()
        if not obuser:
            #nothing to see
            return True
        if self.test_user_has_special_permissions(obuser):
            return True
        if self.use_uc(obuser, uc_name):
            return True
        return False
