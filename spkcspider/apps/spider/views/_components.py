
__all__ = (
    "ComponentIndex", "ComponentAllIndex", "ComponentCreate",
    "ComponentUpdate", "ComponentDelete"
)

from datetime import timedelta
import json
from collections import OrderedDict

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404, redirect
from django.utils.duration import duration_string
from django.db import models
from django.http import HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ._core import UserTestMixin, UCTestMixin
from ..forms import UserComponentForm
from ..contents import installed_contents
from ..models import UserComponent
from ..helpers import get_settings_func


class ComponentAllIndex(ListView):
    model = UserComponent
    is_home = False
    _base_query = models.Q(public=True)
    ordering = ("user", "name")

    def get_queryset(self):
        searchq = models.Q()
        counter = 0
        max_counter = 30  # against ddos
        if "search" in self.request.POST or "info" in self.request.POST:
            for info in self.request.POST.getlist("search"):
                if counter > max_counter:
                    break
                counter += 1
                if len(info) > 0:
                    searchq |= models.Q(contents__info__icontains="%s" % info)

            for info in self.request.POST.getlist("info"):
                if counter > max_counter:
                    break
                counter += 1
                searchq |= models.Q(contents__info__contains="\n%s\n" % info)
        else:
            for info in self.request.GET.getlist("search"):
                if counter > max_counter:
                    break
                counter += 1
                if len(info) > 0:
                    searchq |= models.Q(contents__info__icontains="%s" % info)

            for info in self.request.GET.getlist("info"):
                if counter > max_counter:
                    break
                counter += 1
                searchq |= models.Q(contents__info__contains="\n%s\n" % info)
        if self.request.GET.get("protection", "") == "false":
            searchq &= models.Q(required_passes=0)

        q = self._base_query
        if self.request.user.is_authenticated:
            q |= models.Q(user=self.request.user)
        main_query = self.model.objects.prefetch_related('contents').filter(
            q & searchq
        )
        order = self.get_ordering()
        return main_query.order_by(*order)

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)


class ComponentIndex(UCTestMixin, ListView):
    model = UserComponent
    also_authenticated_users = True
    scope = "list"

    user = None

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["component_user"] = self.user
        kwargs["scope"] = self.scope
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=True):
            return True
        return False

    def get_queryset(self):
        searchq = models.Q()
        counter = 0
        max_counter = 30  # against ddos

        if "search" in self.request.POST or "info" in self.request.POST:
            for info in self.request.POST.getlist("search"):
                if counter > max_counter:
                    break
                counter += 1
                if len(info) > 0:
                    searchq |= models.Q(contents__info__icontains="%s" % info)

            for info in self.request.POST.getlist("info"):
                if counter > max_counter:
                    break
                counter += 1
                searchq |= models.Q(contents__info__contains="\n%s\n" % info)
        else:
            for info in self.request.GET.getlist("search"):
                if counter > max_counter:
                    break
                counter += 1
                if len(info) > 0:
                    searchq |= models.Q(contents__info__icontains="%s" % info)

            for info in self.request.GET.getlist("info"):
                if counter > max_counter:
                    break
                counter += 1
                searchq |= models.Q(contents__info__contains="\n%s\n" % info)
        if self.request.GET.get("protection", "") == "false":
            searchq &= models.Q(required_passes=0)
        searchq &= models.Q(user=self.user)

        return super().get_queryset().filter(searchq).distinct()

    def get_usercomponent(self):
        return get_object_or_404(
            UserComponent, user=self.user, name="index"
        )

    def get_paginate_by(self, queryset):
        if self.scope == "export":
            return None
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)

    def generate_embedded(self, zip, context):
        # Here export only
        ctx = context["context"]
        ctx["request"] = self.request

        deref_level = 1  # don't dereference, as all data will be available
        for component in ctx["object_list"]:
            cname = component.name
            # serialized_obj = protections=serializers.serialize(
            #     'json', component.protections.all()
            # )
            compdic = OrderedDict(
                name=cname
            )
            compdic["public"] = component.public,
            compdic["required_passes"] = \
                component.required_passes
            compdic["token_duration"] = \
                duration_string(component.token_duration)

            zip.writestr(
                "{}/data.json".format(cname), json.dumps(compdic)
            )
            for n, content in enumerate(
                component.contents.order_by("ctype__name", "id")
            ):
                contdic = OrderedDict(
                    pk=content.pk,
                    ctype=content.ctype.name,
                    info=content.info
                )
                ctx["uc"] = self.usercomponent
                content.content.extract_form(
                    ctx, contdic, zip, level=deref_level,
                    prefix="{}/{}/".format(cname, n)
                )
                zip.writestr(
                    "{}/{}/data.json".format(cname, n), json.dumps(contdic)
                )

    def render_to_response(self, context):
        if self.scope != "export":
            return super().render_to_response(context)
        maindic = {"scope": "export"}
        return get_settings_func(
            "GENERATE_EMBEDDED_FUNC",
            "spkcspider.apps.spider.helpers.generate_embedded"
        )(
            self.generate_embedded, locals()
        )


class ComponentCreate(UserTestMixin, CreateView):
    model = UserComponent
    form_class = UserComponentForm
    also_authenticated_users = True
    no_nonce_usercomponent = True

    def get_success_url(self):
        return reverse(
            "spider_base:ucomponent-update", kwargs={
                "name": self.object.name,
                "nonce": self.object.nonce
            }
        )

    def get_usercomponent(self):
        query = {"name": "index"}
        query["user"] = self.get_user()
        return get_object_or_404(UserComponent, **query)

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["instance"] = self.model(user=self.get_user())
        return ret


class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    form_class = UserComponentForm
    also_authenticated_users = True

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, user=self.get_user(), name=self.kwargs["name"],
            nonce=self.kwargs["nonce"]
        )

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'instance': self.object
        }

    def form_valid(self, form):
        self.object = form.save()
        if self.kwargs["nonce"] != self.object.nonce:
            return redirect(
                "spider_base:ucomponent-update", kwargs={
                    "name": self.object.name,
                    "nonce": self.object.nonce
                }
            )
        return self.render_to_response(
            self.get_context_data(
                form=self.get_form_class()(**self.get_form_success_kwargs())
            )
        )


class ComponentDelete(UserTestMixin, DeleteView):
    model = UserComponent
    fields = []
    object = None
    http_method_names = ['get', 'post', 'delete']

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.user = self.get_user()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        username = getattr(self.user, self.user.USERNAME_FIELD)
        return reverse(
            "spider_base:ucomponent-list", kwargs={
                "user": username
            }
        )

    def get_required_timedelta(self):
        _time = getattr(
            settings, "DELETION_PERIODS_COMPONENTS", {}
        ).get(self.object.name, None)
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_context_data(self, **kwargs):
        _time = self.get_required_timedelta()
        if _time and self.object.deletion_requested:
            now = timezone.now()
            if self.object.deletion_requested + _time >= now:
                kwargs["remaining"] = timedelta(seconds=0)
            else:
                kwargs["remaining"] = self.object.deletion_requested+_time-now
        return super().get_context_data(**kwargs)

    def delete(self, request, *args, **kwargs):
        # hack for compatibility to ContentRemove
        if getattr(self.object, "name", "") == "index":
            return self.handle_no_permission()
        _time = self.get_required_timedelta()
        if _time:
            now = timezone.now()
            if self.object.deletion_requested:
                if self.object.deletion_requested+_time >= now:
                    return self.get(request, *args, **kwargs)
            else:
                self.object.deletion_requested = now
                self.object.save()
                return self.get(request, *args, **kwargs)
        self.object.delete()
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        # because forms are screwed (delete not possible)
        if request.POST.get("action") == "reset":
            return self.reset(request, *args, **kwargs)
        elif request.POST.get("action") == "delete":
            return self.delete(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def reset(self, request, *args, **kwargs):
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, user=self.user, name=self.kwargs["name"],
            nonce=self.kwargs["nonce"]
        )
