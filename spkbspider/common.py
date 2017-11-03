
from django.contrib.auth.mixins import UserPassesTestMixin


class ObjectTestMixin(UserPassesTestMixin):
    object = None
    def get_object(self, queryset=None):
        if self.object:
            return self.object
        elif hasattr(self, "get_object2"):
            return self.get_object2(queryset)
        else:
            return super().get_object(queryset)

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
