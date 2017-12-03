from django.shortcuts import render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone

from datetime import timedelta

from .forms import UserComponentForm



from .models import UserComponent, UserContent
from .contents import installed_contents

class UserTestMixin(UserPassesTestMixin):

    # by default only owner can access view
    def test_func(self):
        if self.request.user == self.get_user():
            return True
        return False

    def test_user_has_special_permissions(self):
        if not self.request.user.is_active or not self.request.user.is_authenticated:
            return False
        if self.request.user == self.get_user():
            return True
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        return False

    def get_user(self):
        return get_object_or_404(get_user_model(), username=self.kwargs["user"])

    def get_usercomponent(self):
        return get_object_or_404(UserComponent, user=self.get_user(), name=self.kwargs["name"])

    #def get_noperm_template_names(self):
    #    return [self.noperm_template_name]

    #def handle_no_permission(self):
    #    raise PermissionDenied(self.get_permission_denied_message())

class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        user_test_result = self.get_test_func()()
        if not user_test_result:
            return self.handle_no_permission()
        return super(UserTestMixin, self).dispatch(request, *args, **kwargs)



class ComponentAllIndex(ListView):
    model = UserComponent

    def get_queryset(self):
        if self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser):
            return self.model.all()
        return self.model.filter(models.Q(protected_by=[])|models.Q(user=self.request.user))

class ComponentIndex(UCTestMixin, ListView):
    model = UserComponent

    def test_func(self):
        if self.test_user_has_special_permissions():
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(user=self.get_user())

    def get_usercomponent(self):
        return get_object_or_404(UserComponent, user=self.get_user(), name="index")

class ComponentCreate(PermissionRequiredMixin, UserTestMixin, CreateView):
    model = UserComponent
    permission_required = 'add_{}'.format(model._meta.model_name)
    fields = ['name', 'data', 'protections']

class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    fields = ['name', 'data', 'protections']
    form_class = UserComponentForm

    def get_form_kwargs(self, **kwargs):
        cargs = super().get_form_kwargs(**kwargs)
        cargs["protection_forms"] = self.object.settings()
        return cargs

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        kwargs["assigned"] = self.object.contents.all()
        return super().get_context_data(**kwargs)

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user=self.get_user(), name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user=self.get_user(), name=self.kwargs["name"])

class ComponentDelete(UserTestMixin, DeleteView):
    model = UserComponent

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, user=self.get_user(), name=self.kwargs["name"])
        else:
            return get_object_or_404(self.get_queryset(), user=self.get_user(), name=self.kwargs["name"])


################################################################################


class ContentIndex(UCTestMixin, ListView):
    model = UserContent

    def test_func(self):
        if self.test_user_has_special_permissions():
            return True
        return False

    def get_queryset(self):
        return self.model.objects.filter(usercomponent=self.usercomponent)


class ContentAdd(PermissionRequiredMixin, UCTestMixin, CreateView):
    model = UserContent
    permission_required = 'add_{}'.format(model._meta.model_name)

    def get_form_class(self):
        try:
            return installed_contents[self.kwargs["type"]]
        except KeyError:
            raise Http404('%s matches no available content (hint: blacklisted?)' % self.kwargs["type"])
    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        content = form.save()
        try:
            if hasattr(form, "get_info"):
                self.object = UserContent.objects.create(usercomponent=self.usercomponent, content=content, info=form.get_info(self.usercomponent))
            else:
                self.object = UserContent.objects.create(usercomponent=self.usercomponent, content=content)
        except Exception as exc:
            content.delete()
            raise exc
        return HttpResponseRedirect(self.get_success_url())

class ContentUpdate(UCTestMixin, UpdateView):
    model = UserContent

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset.exclude(info__contains="noupdate;"), usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset().exclude(info__contains="noupdate;"), usercomponent=self.usercomponent, id=self.kwargs["id"])

    def get_form_class(self):
        return self.object.content.form

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super().get_form_kwargs()
        if hasattr(self, 'object'):
            kwargs.update({'instance': self.object.content})
        return kwargs

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save().associated
        if hasattr(form, "get_info"):
            self.object.info = form.get_info(self.usercomponent)
            self.object.save(update_fields=["info"])
        return HttpResponseRedirect(self.get_success_url())

class ContentResetRemove(UCTestMixin, UpdateView):
    model = UserContent
    fields = []
    http_method_names = ['post']
    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.usercomponent, id=self.kwargs["id"])
    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.instance
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())


class ContentRemove(UCTestMixin, DeleteView):
    model = UserContent

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        _time = self.object.get_value("protected_for")
        if _time:
            now = timezone.now()
            _time = timedelta(seconds=_time)
            if self.object.deletion_requested:
                if self.object.deletion_requested+_time>now:
                    return self.get(request, *args, **kwargs)
            else:
                self.object.deletion_requested = now
                self.object.save()
                return self.get(request, *args, **kwargs)
        self.object.delete()
        return HttpResponseRedirect(success_url)

    def get_object(self, queryset=None):
        if queryset:
            return get_object_or_404(queryset, usercomponent=self.usercomponent, id=self.kwargs["id"])
        else:
            return get_object_or_404(self.get_queryset(), usercomponent=self.usercomponent, id=self.kwargs["id"])
