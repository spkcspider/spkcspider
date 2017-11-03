
from django.contrib.auth.mixins import UserPassesTestMixin


class ObjectTestMixin(UserPassesTestMixin):
    object = None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
