from django.contrib.auth.decorators import login_required
from django.urls import path

from .views import (
    OwnerTokenManagement, ComponentCreate, ComponentIndex,
    ComponentPublicIndex, ComponentUpdate, ConfirmTokenUpdate, ContentAccess,
    ContentAdd, ContentIndex, EntityMassDeletion, RequestTokenUpdate,
    TokenDeletionRequest, TokenRenewal, TravelProtectionManagement
)

app_name = "spider_base"

# components plural: most components url retrieve multiple items
#    one "component"-url for single retrievals is confusing

urlpatterns = [
    path(
        'components/export/',
        login_required(ComponentIndex.as_view(scope="export")),
        name='ucomponent-export'
    ),
    path(
        'components/slug:user>/export/',
        login_required(ComponentIndex.as_view(scope="export")),
        name='ucomponent-export'
    ),
    path(
        'components/list/',
        login_required(ComponentIndex.as_view()),
        name='ucomponent-list'
    ),
    path(
        'components/list/<slug:user>/',
        login_required(ComponentIndex.as_view()),
        name='ucomponent-list'
    ),
    # path(
    #     'ucs/create/<slug:user>/',
    #     ComponentCreate.as_view(),
    #     name='ucomponent-add'
    # ),
    path(
        'components/add/',
        login_required(ComponentCreate.as_view()),
        name='ucomponent-add'
    ),
    path(
        'components/<str:token>/update/',
        login_required(ComponentUpdate.as_view()),
        name='ucomponent-update'
    ),
    path(
        'components/<str:token>/delete/',
        EntityMassDeletion.as_view(),
        name='entity-delete'
    ),

    path(
        'components/<str:token>/list/',
        ContentIndex.as_view(),
        name='ucontent-list'
    ),
    path(
        'components/<str:token>/export/',
        ContentIndex.as_view(scope="export"),
        name='ucontent-export'
    ),
    path(
        'components/<str:token>/add/<slug:type>/',
        ContentAdd.as_view(),
        name='ucontent-add'
    ),
    path(
        'content/<str:token>/<slug:access>/',
        ContentAccess.as_view(),
        name='ucontent-access'
    ),
    path(
        'token/<str:token>/delete/',
        OwnerTokenManagement.as_view(scope="delete"),
        name='token-owner-delete'
    ),
    path(
        'token/<str:token>/share/',
        OwnerTokenManagement.as_view(scope="share"),
        name='token-owner-share'
    ),
    path(
        'token/confirm-update-request/',
        ConfirmTokenUpdate.as_view(),
        name='token-confirm-update-request'
    ),
    path(
        'token/update-request/',
        RequestTokenUpdate.as_view(),
        name='token-update-request'
    ),
    path(
        'token/delete-request/',
        TokenDeletionRequest.as_view(),
        name='token-delete-request'
    ),
    path(
        'token/renew/',
        TokenRenewal.as_view(),
        name='token-renew'
    ),
    path(
        'travelprotection/',
        TravelProtectionManagement.as_view(),
        name='travelprotection-manage'
    ),
    path(
        'components/',
        ComponentPublicIndex.as_view(
            is_home=False
        ),
        name='ucomponent-listpublic'
    ),
]
