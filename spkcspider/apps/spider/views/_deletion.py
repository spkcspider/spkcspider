""" Deletion Views """

__all__ = (
    "MassDeletion"
)

import json
from itertools import chain

from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.views.generic.base import TemplateView
from spkcspider.constants import loggedin_active_tprotections

from ..models import AssignedContent, UserComponent

from ._core import UserTestMixin


class MassDeletion(UserTestMixin, TemplateView):

    def options(self, request, *args, **kwargs):
        ret = super().options(request, *args, **kwargs)
        ret["Access-Control-Allow-Origin"] = self.request.get_host()
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def calculate_deletion_content(self, del_requested, content):
        if content.deletion_requested:
            return {
                "ob": content,
                "deletion_date":
                    content.deletion_requested+content.deletion_period,
                "deletion_in_progress": True
            }
        else:
            return {
                "ob": content,
                "deletion_date": del_requested+content.deletion_period,
                "deletion_in_progress": False
            }

    def calculate_deletion_component(self, uc, now, q, log=None):
        del_requested = uc.deletion_requested or now

        if log is not None:
            def _helper(self, content):
                ret = self.calculate_deletion_content(del_requested, content)
                log[content.id] = ret
                return ret["deletion_date"]
        else:
            def _helper(self, content):
                return self.calculate_deletion_content(
                    del_requested, content
                )["deletion_date"]
        return max(
            chain.from_iterable(
                [del_requested + uc.deletion_period],
                map(
                    _helper, uc.contents.filter(q)
                )
            )
        )

    def post(self, request, *args, **kwargs):
        now = timezone.now()
        if request.content_type == "application/json":
            json_data = json.loads(request.body)
            delete_components = json_data.get("delete_components", [])
            reset_components = json_data.get("reset_components", [])
            delete_contents = json_data.get("delete_contents", [])
            reset_contents = json_data.get("reset_contents", [])
        else:
            delete_components = request.POST.getlist("delete_components")
            reset_components = request.POST.getlist("reset_components")
            delete_contents = request.POST.getlist("delete_contents")
            reset_contents = request.POST.getlist("reset_contents")
        try:
            reset_components = set(map(int, reset_components))
            delete_components = set(map(
                int, delete_components
            )).difference_update(reset_components)
            reset_contents = set(map(int, reset_contents))
            delete_contents = set(map(
                int, delete_contents
            )).difference_update(reset_contents)

        except Exception:
            return HttpResponse(status=400)

        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )

        travel_contents_q = (
            models.Q(travel_protected__in=travel) |
            models.Q(usercomponent__travel_protected__in=travel)
        )

        components = {}

        component_query = UserComponent.objects.exclude(
            travel_protected__in=travel
        )
        if not self.usercomponent.is_index:
            component_query.filter(id=self.usercomponent.id)
        else:
            component_query.filter(user=self.usercomponent.user)

        for uc in component_query:
            item = {
                "ob": uc,
                "contents": {},
                "deletion_in_progress":
                    uc.id in delete_components and not uc.is_index
            }

            item["deletion_date"] = \
                self.calculate_deletion_component(
                    uc, now, ~travel_contents_q, item["contents"]
                )
            if item["deletion_in_progress"] and item["deletion_date"] <= now:
                uc.delete()
                continue

            for content in uc.contents.filter(
                ~travel_contents_q,
                id__in=delete_contents
            ):
                if item["contents"][content.id]["deletion_date"] <= now:
                    content.delete()
                    del item["contents"][content.id]
                else:
                    item["contents"][content.id]["deletion_in_progress"] = \
                        True
            components[uc.name] = item

        component_query.filter(id__in=delete_components).update(
            deletion_requested=now
        )
        component_query.filter(id__in=reset_components).update(
            deletion_requested=None
        )
        content_query = AssignedContent.objects.filter(
            ~travel_contents_q
        ).exclude(usercomponent__in=component_query)
        content_query.filter(id__in=delete_contents).update(
            deletion_requested=now
        )
        content_query.filter(id__in=reset_contents).update(
            deletion_requested=None
        )

        return self.render_to_response(self.get_context_data(
            hierarchy=components
        ))

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )

        travel_contents_q = (
            models.Q(travel_protected__in=travel) |
            models.Q(usercomponent__travel_protected__in=travel)
        )

        components = {}

        component_query = UserComponent.objects.exclude(
            travel_protected__in=travel
        )
        if not self.usercomponent.is_index:
            component_query.filter(id=self.usercomponent.id)
        else:
            component_query.filter(user=self.usercomponent.user)

        for uc in component_query:
            item = {
                "ob": uc,
                "contents": {},
                "deletion_in_progress": uc.deletion_requested is not None
            }
            item["deletion_date"] = \
                self.calculate_deletion_component(
                    uc, now, ~travel_contents_q, item["contents"]
                )
        return self.render_to_response(self.get_context_data(
            hierarchy=components
        ))

    def render_to_response(self, context):
        if self.request.GET.get("raw", "") == "json":
            # last time it is used
            for component_val in context["hierarchy"].values():
                component_val.pop("ob")
                for val in component_val["contents"].values():
                    val.pop("ob")
            return JsonResponse(
                context["hierarchy"]
            )
        return super().render_to_response(context)
