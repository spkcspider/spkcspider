""" Deletion Views """

__all__ = (
    "EntityMassDeletion",
)

import json

from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import (
    Http404, HttpResponse, HttpResponseGone, HttpResponsePermanentRedirect,
    JsonResponse
)
from django.urls import reverse
from django.utils import timezone
from django.views.generic.base import TemplateView

from spkcspider.apps.spider.queryfilters import loggedin_active_tprotections_q

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
        kwargs["selected_components"] = set(self.request.GET.getlist("uc"))
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
            loggedin_active_tprotections_q
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
                user=user
            )

        content_query = AssignedContent.objects.filter(
            usercomponent__user=user
        )

        ignored_content_ids = frozenset(
            content_query.filter(
                travel_contents_q
            ).values_list("id", flat=True)
        )
        ignored_component_ids = frozenset(
            component_query.filter(
                travel_protected__in=travel
            ).values_list("id", flat=True)
        )

        for uc in component_query:
            item = {
                "ob": uc,
                "contents": {},
                "deletion_active": uc.deletion_requested is not None
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
            reset_components = set(reset_components)
            delete_components = set(delete_components)
            delete_components.difference_update(reset_components)
            reset_contents = set(map(int, reset_contents))
            delete_contents = set(map(
                int, delete_contents
            ))
            delete_contents.difference_update(reset_contents)

        except Exception:
            return HttpResponse(status=400)

        travel = self.get_travel_for_request().filter(
            loggedin_active_tprotections_q
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
                user=user
            )

        content_query = AssignedContent.objects.filter(
            usercomponent__user=user
        )

        ignored_content_ids = frozenset(
            content_query.filter(
                travel_contents_q
            ).values_list("id", flat=True)
        )
        ignored_component_ids = frozenset(
            component_query.filter(
                travel_protected__in=travel
            ).values_list("id", flat=True)
        )

        delete_contents.difference_update(ignored_content_ids)
        reset_contents.difference_update(ignored_content_ids)

        if self.request.user == self.usercomponent.user:
            component_query.exclude(id__in=ignored_component_ids).filter(
                name__in=delete_components,
                deletion_requested__isnull=True
            ).update(
                deletion_requested=now
            )
            component_query.exclude(id__in=ignored_component_ids).filter(
                name__in=reset_components
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
                "deletion_active":
                    (
                        uc.name in delete_components or
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
            if "application/json" in (
                self.request.headers.get("accept"), self.request.content_type
            ):
                # last time it is used
                for component_val in context["hierarchy"].values():
                    component_val["name"] = component_val["ob"].name
                    component_val["description"] = \
                        component_val["ob"].description
                    component_val.pop("ob")
                    for content_val in component_val["contents"].values():
                        content_val["name"] = content_val["ob"].name
                        content_val["description"] = \
                            content_val["ob"].description
                        content_val.pop("ob")
                response = JsonResponse(context["hierarchy"])
            else:
                response = super().render_to_response(context)
        elif self.request.user.is_authenticated:
            # last resort: redirect to index
            index = self.request.user.usercomponent_set.get("index")
            response = HttpResponsePermanentRedirect(
                "{}?{}".format(
                    reverse(
                        'spider_base:entity-delete',
                        kwargs={"token": index.token}
                    ), context["sanitized_GET"]
                )
            )
        else:
            response = HttpResponseGone()
        response["Access-Control-Allow-Origin"] = self.request.get_host()
        response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return response
