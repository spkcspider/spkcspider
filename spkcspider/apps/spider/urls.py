from django.urls import path
from django.contrib.auth.decorators import login_required


from .views import (
    ComponentIndex, ComponentPublicIndex, ComponentCreate,
    ComponentUpdate, ComponentDelete
)

from .views import (
    ContentAdd, ContentIndex, ContentAccess, ContentDelete,
    TravelProtectionManagement
)

from .views import (
    AdminTokenManagement, TokenDeletionRequest, TokenRenewal
)

app_name = "spider_base"

# token: path: token can simulate path structures (legacy)

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
        login_required(ComponentDelete.as_view()),
        name='ucomponent-delete'
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
        'content/<str:token>/delete/',
        ContentDelete.as_view(),
        name='ucontent-delete'
    ),
    path(
        'content/<str:token>/<slug:access>/',
        ContentAccess.as_view(),
        name='ucontent-access'
    ),
    path(
        'token/<str:token>/delete/',
        AdminTokenManagement.as_view(scope="delete"),
        name='token-admin-delete'
    ),
    path(
        'token/<str:token>/share/',
        AdminTokenManagement.as_view(scope="share"),
        name='token-admin-share'
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
