
__all__ = (
    "ComponentIndex", "ComponentPublicIndex", "ComponentCreate",
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
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ._core import UserTestMixin, UCTestMixin
from ..constants.static import index_names
from ..forms import UserComponentForm
from ..contents import installed_contents
from ..models import UserComponent, TravelProtection
from ..helpers import get_settings_func


class ComponentPublicIndex(ListView):
    model = UserComponent
    is_home = False
    allowed_GET_parameters = set(["protection", "raw"])

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = True
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )

        GET = self.request.GET.copy()
        # parameters preserved in search
        for key in list(GET.keys()):
            if key not in self.allowed_GET_parameters:
                GET.pop(key, None)
        kwargs["spider_GET"] = GET
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        searchq = models.Q()
        searchq_exc = models.Q()
        infoq = models.Q()
        infoq_exc = models.Q()
        counter = 0
        max_counter = 30  # against ddos
        if "search" in self.request.POST or "info" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
            infolist = self.request.POST.getlist("info")
        else:
            searchlist = self.request.GET.getlist("search")
            infolist = self.request.GET.getlist("info")

        for item in searchlist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                _item = item[1:]
            elif item.startswith("!"):
                _item = item[1:]
            else:
                _item = item
            qob = models.Q(
                contents__info__icontains="%s" % _item
            )
            qob |= models.Q(
                description__icontains="%s" % _item
            )
            qob |= models.Q(
                name__icontains="%s" % _item
            )
            if item.startswith("!!"):
                searchq |= qob
            elif item.startswith("!"):
                searchq_exc |= qob
            else:
                searchq |= qob

        for item in infolist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                infoq |= models.Q(contents__info__contains="\n%s\n" % item[1:])
            elif item.startswith("!"):
                infoq_exc |= models.Q(
                    contents__info__contains="\n%s\n" % item[1:]
                )
            else:
                infoq |= models.Q(contents__info__contains="\n%s\n" % item)
        if self.request.GET.get("protection", "") == "false":
            searchq &= models.Q(required_passes=0)

        q = models.Q(public=True)
        if self.is_home:
            q &= models.Q(featured=True)
        main_query = self.model.objects.prefetch_related(
            "contents"
        ).filter(
            q & searchq & ~searchq_exc & infoq & ~infoq_exc
        ).order_by(*self.get_ordering()).distinct()
        return main_query

    def get_paginate_by(self, queryset):
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)

    def get_ordering(self):
        if self.is_home:
            return ("modified",)
        else:
            return ("user", "modified")

    def render_to_response(self, context):
        # NEVER: allow embedding, things get much too big
        if self.request.GET.get("raw", "") != "true":
            return super().render_to_response(context)
        return JsonResponse({
            "components": [
                {
                    "user": item.username,
                    "name": (
                        item.name if item.name != "fake_index" else "index"
                    ),
                    "link": "{}{}?{}".format(
                        context["hostpart"],
                        reverse(
                            "spider_base:ucontent-list",
                            kwargs={
                                "id": item.id, "nonce": item.nonce
                            }
                        ),
                        context["spider_GET"].urlencode()
                    )
                }
                for item in context["object_list"]
            ],
            "scope": "list"
        })


class ComponentIndex(UCTestMixin, ListView):
    model = UserComponent
    also_authenticated_users = True
    no_nonce_usercomponent = True
    scope = "list"

    user = None

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_ordering(self):
        # if self.scope != "export":
        #     return ("modified",)
        return ("id",)

    def get_context_data(self, **kwargs):
        kwargs["component_user"] = self.user
        kwargs["username"] = getattr(self.user, self.user.USERNAME_FIELD)
        kwargs["scope"] = self.scope
        kwargs["is_public_view"] = False
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=True):
            return True
        return False

    def get_queryset(self):
        searchq = models.Q()
        searchq_exc = models.Q()
        infoq = models.Q()
        infoq_exc = models.Q()
        counter = 0
        # against ddos
        max_counter = getattr(settings, "MAX_SEARCH_PARAMETERS", 30)

        if "search" in self.request.POST or "info" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
            infolist = self.request.POST.getlist("info")
        else:
            searchlist = self.request.GET.getlist("search")
            infolist = self.request.GET.getlist("info")

        for item in searchlist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                _item = item[1:]
            elif item.startswith("!"):
                _item = item[1:]
            else:
                _item = item
            qob = models.Q(
                contents__info__icontains="%s" % _item
            )
            qob |= models.Q(
                description__icontains="%s" % _item
            )
            qob |= models.Q(
                name__icontains="%s" % _item
            )
            if item.startswith("!!"):
                searchq |= qob
            elif item.startswith("!"):
                searchq_exc |= qob
            else:
                searchq |= qob

        for item in infolist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                infoq |= models.Q(contents__info__contains="\n%s\n" % item[1:])
            elif item.startswith("!"):
                infoq_exc |= models.Q(
                    contents__info__contains="\n%s\n" % item[1:]
                )
            else:
                infoq |= models.Q(contents__info__contains="\n%s\n" % item)
        if self.request.GET.get("protection", "") == "false":
            searchq &= models.Q(required_passes=0)
        searchq &= (
            infoq & ~searchq_exc & ~infoq_exc &
            models.Q(user=self.user)
        )

        # doesn't matter if it is same user, lazy
        travel = TravelProtection.objects.get_active()
        # remove all travel protected if user
        if self.request.user == self.user:
            searchq &= ~models.Q(
                travel_protected__in=travel
            )
            now = timezone.now()
            searchq &= ~(
                # exclude future events
                models.Q(
                    contents__modified__lte=now,
                    contents__info__contains="\ntype=TravelProtection\n"
                )
            )
        if self.request.session.get("is_fake", False):
            searchq &= ~models.Q(name="index")
        else:
            searchq &= ~models.Q(name="fake_index")

        return super().get_queryset().prefetch_related(
            'contents'
        ).filter(searchq).distinct()

    def get_usercomponent(self):
        ucname = "index"
        if self.request.session.get("is_fake", False):
            ucname = "fake_index"
        return get_object_or_404(
            UserComponent, user=self.user, name=ucname
        )

    def get_paginate_by(self, queryset):
        if self.scope == "export":
            return None
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)

    def generate_embedded(self, zip, context):
        # Here export only
        store_dict = OrderedDict(
            ctype="Index",
        )
        zip.writestr(
            "data.json", json.dumps(store_dict)
        )

        deref_level = 1  # don't dereference, as all data will be available
        for component in context["context"]["object_list"]:
            cname = component.name
            if cname == "fake_index":
                cname = "index"
            # serialized_obj = protections=serializers.serialize(
            #     'json', component.protections.all()
            # )
            comp_dict = OrderedDict(
                name=cname
            )
            comp_dict["public"] = component.public,
            comp_dict["required_passes"] = \
                component.required_passes
            comp_dict["token_duration"] = \
                duration_string(component.token_duration)

            zip.writestr(
                "{}/data.json".format(cname), json.dumps(comp_dict)
            )
            for n, content in enumerate(
                component.contents.order_by("id")
            ):
                context["content"] = content.content
                store_dict = OrderedDict(
                    pk=content.get_id(),
                    ctype=content.getlist("type", 1)[0],
                    ref_fields=[],
                    info=content.info,
                    scope="export",
                    modified=content.modified.strftime(
                        "%a, %d %b %Y %H:%M:%S %z"
                    ),
                )
                context["store_dict"] = store_dict
                context["uc"] = component
                content.content.extract_form(
                    context, store_dict, zip, level=deref_level,
                    prefix="{}/{}/".format(cname, n)
                )
                zip.writestr(
                    "{}/{}/data.json".format(cname, n), json.dumps(store_dict)
                )

    def render_to_response(self, context):
        if self.scope != "export":
            return super().render_to_response(context)
        session_dict = {
            "request": self.request,
            "context": context,
            "scope": context["scope"],
            "expires": None,
            "hostpart": context["hostpart"]
        }

        return get_settings_func(
            "GENERATE_EMBEDDED_FUNC",
            "spkcspider.apps.spider.functions.generate_embedded"
        )(self.generate_embedded, session_dict, None)


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
        query = {}
        if self.request.session.get("is_fake", False):
            query["name"] = "fake_index"
        else:
            query["name"] = "index"
        query["user"] = self.get_user()
        return get_object_or_404(UserComponent, **query)

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["instance"] = self.model(user=self.get_user())
        ret['request'] = self.request
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
            queryset.prefetch_related(
                "protections",
            ),
            user=self.get_user(), name=self.kwargs["name"],
            nonce=self.kwargs["nonce"]
        )

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret['request'] = self.request
        return ret

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'instance': self.object,
            'request': self.request
        }

    def form_valid(self, form):
        self.object = form.save()
        if (
            self.kwargs["nonce"] != self.object.nonce or
            self.kwargs["name"] != self.object.name
        ):
            return redirect(
                "spider_base:ucomponent-update",
                name=self.object.name,
                nonce=self.object.nonce
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
        self.user = self.get_user()
        self.object = self.get_object()
        self.usercomponent = self.object
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        username = getattr(self.user, self.user.USERNAME_FIELD)
        return reverse(
            "spider_base:ucomponent-list", kwargs={
                "user": username
            }
        )

    def get_required_timedelta(self):
        # TODO: needs better design
        _time = getattr(
            settings, "DELETION_PERIODS_COMPONENTS", {}
        ).get(self.object.name, None)
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
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
        if getattr(self.object, "name", "") in index_names:
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
