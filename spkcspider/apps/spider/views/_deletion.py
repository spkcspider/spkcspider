""" Deletion Views """

__all__ = (
    "EntityMassDeletion",
)

import json

from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic.base import TemplateView

from spkcspider.constants import loggedin_active_tprotections

from ..models import AssignedContent, UserComponent
from ._core import UCTestMixin


class EntityMassDeletion(UCTestMixin, TemplateView):
    """
        Delete Contents and Usercomponents
    """
    preserved_GET_parameters = {"token", "search", "id"}
    own_marked_for_deletion = False
    template_name = "spider_base/entity_mass_deletion.html"

    @staticmethod
    def to_int(value):
        try:
            return int(value)
        except ValueError:
            return None

    def get_context_data(self, **kwargs):
        kwargs["selected_components"] = set(map(
            self.to_int, self.request.GET.getlist("ucid")
        ))
        kwargs["selected_contents"] = set(map(
            self.to_int, self.request.GET.getlist("cid")
        ))
        return super().get_context_data(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied:
            raise Http404()

    def test_func(self):
        return self.has_special_access(
            user_by_login=True, user_by_token=True,
            staff=False, superuser=False
        )

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        user = self.usercomponent.user
        travel = self.get_travel_for_request().filter(
            login_protection__in=loggedin_active_tprotections
        )

        travel_contents_q = (
            models.Q(travel_protected__in=travel) |
            models.Q(usercomponent__travel_protected__in=travel)
        )

        components = {}

        if not self.usercomponent.is_index:
            component_query = UserComponent.objects.filter(
                id=self.usercomponent.id
            )
        else:
            component_query = UserComponent.objects.filter(
                user=self.usercomponent.user
            )

        content_query = AssignedContent.objects.filter(
            usercomponent__user=user
        )

        ignored_content_ids = frozenset(
            content_query.filter(
                travel_contents_q
            ).values_list("id", flat=True)
        )
        ignored_component_ids = component_query.filter(
            travel_protected__in=travel
        )

        for uc in component_query:
            item = {
                "ob": uc,
                "contents": {},
                "deletion_in_progress": uc.deletion_requested is not None
            }
            item["deletion_date"] = \
                self.calculate_deletion_component(
                    uc,
                    now,
                    ignored_content_ids,
                    log=item["contents"],
                    del_expired=True
                )

            if item["deletion_date"] is None:
                if uc == self.usercomponent:
                    self.own_marked_for_deletion = True
                continue
            if uc.id not in ignored_component_ids:
                components[uc.name] = item
        return self.render_to_response(self.get_context_data(
            hierarchy=components,
            now=now,
            ignored_component_ids=ignored_component_ids
        ))

    def post(self, request, *args, **kwargs):
        now = timezone.now()
        user = self.usercomponent.user
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
            ))
            delete_components.difference_update(reset_components)
            reset_contents = set(map(int, reset_contents))
            delete_contents = set(map(
                int, delete_contents
            ))
            delete_contents.difference_update(reset_contents)

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

        if not self.usercomponent.is_index:
            component_query = UserComponent.objects.filter(
                id=self.usercomponent.id
            )
        else:
            component_query = UserComponent.objects.filter(
                user=self.usercomponent.user
            )

        content_query = AssignedContent.objects.filter(
            usercomponent__user=user
        )

        ignored_content_ids = frozenset(
            content_query.filter(
                travel_contents_q
            ).values_list("id", flat=True)
        )
        ignored_component_ids = component_query.filter(
            travel_protected__in=travel
        )

        delete_components.difference_update(ignored_component_ids)
        reset_components.difference_update(ignored_component_ids)
        delete_contents.difference_update(ignored_content_ids)
        reset_contents.difference_update(ignored_content_ids)

        component_query.exclude(id__in=ignored_component_ids).filter(
            id__in=delete_components,
            deletion_requested__isnull=True
        ).update(
            deletion_requested=now
        )
        component_query.exclude(id__in=ignored_component_ids).filter(
            id__in=reset_components
        ).update(
            deletion_requested=None
        )
        content_query.exclude(
            id__in=ignored_content_ids
        ).filter(
            id__in=delete_contents,
            deletion_requested__isnull=True
        ).update(
            deletion_requested=now
        )
        content_query.exclude(
            id__in=ignored_content_ids
        ).filter(id__in=reset_contents).update(
            deletion_requested=None
        )

        for uc in component_query:
            item = {
                "ob": uc,
                "contents": {},
                "deletion_in_progress":
                    (
                        uc.id in delete_components or
                        uc.deletion_requested
                    ) and not uc.is_index
            }

            item["deletion_date"] = \
                self.calculate_deletion_component(
                    uc, now, ignored_content_ids, item["contents"],
                    del_expired=True
                )
            if item["deletion_date"] is None:
                if uc == self.usercomponent:
                    self.own_marked_for_deletion = True
                continue

            if uc.id not in ignored_component_ids:
                components[uc.name] = item

        return self.render_to_response(self.get_context_data(
            hierarchy=components,
            now=now,
            ignored_component_ids=ignored_component_ids
        ))

    def options(self, request, *args, **kwargs):
        ret = super().options(request, *args, **kwargs)
        ret["Access-Control-Allow-Origin"] = self.request.get_host()
        ret["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return ret

    def render_to_response(self, context):
        if not self.own_marked_for_deletion:
            if self.request.GET.get("raw", "") == "json":
                # last time it is used
                for component_val in context["hierarchy"].values():
                    component_val.pop("ob")
                    for val in component_val["contents"].values():
                        val.pop("ob")
                response = JsonResponse(
                    context["hierarchy"]
                )
            else:
                response = super().render_to_response(context)
        elif (
            self.request.user.is_authenticated and
            # don't blow cover
            self.usercomponent.id not in context["ignored_component_ids"]
        ):
            response = redirect(
                'spider_base:entity-delete', permanent=True,
                token=self.object.token, access="update"
            )
        else:
            response = HttpResponse(404)
        response["Access-Control-Allow-Origin"] = self.request.get_host()
        response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return response
