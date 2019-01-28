from django.urls import path
from django.contrib.auth.decorators import login_required


from .views import (
    ComponentIndex, ComponentPublicIndex, ComponentCreate,
    ComponentUpdate, ComponentDelete
)

from .views import (
    ContentAdd, ContentIndex, ContentAccess, ContentRemove
)

from .views import (
    TokenDelete, TokenDeletionRequest, TokenRenewal
)

app_name = "spider_base"

# uc = UserComponent
# name = UserComponent.name
# UserComponent.name contains unicode => str

urlpatterns = [
    path(
        'ucs/user/<slug:user>/export/',
        login_required(ComponentIndex.as_view(scope="export")),
        name='ucomponent-export'
    ),
    path(
        'ucs/user/<slug:user>/',
        login_required(ComponentIndex.as_view()),
        name='ucomponent-list'
    ),
    path(
        'ucs/user/',
        login_required(ComponentIndex.as_view()),
        name='ucomponent-list'
    ),
    # path(
    #     'ucs/create/<slug:user>/',
    #     ComponentCreate.as_view(),
    #     name='ucomponent-create'
    # ),
    path(
        'ucs/create/',
        login_required(ComponentCreate.as_view()),
        name='ucomponent-create'
    ),
    path(
        'ucs/update/<slug:user>/<str:name>/<path:token>/',
        login_required(ComponentUpdate.as_view()),
        name='ucomponent-update'
    ),
    path(
        'ucs/update/<str:name>/<path:token>/',
        login_required(ComponentUpdate.as_view()),
        name='ucomponent-update'
    ),
    path(
        'ucs/delete/<slug:user>/<str:name>/<path:token>/',
        login_required(ComponentDelete.as_view()),
        name='ucomponent-delete'
    ),
    path(
        'token/delete/<str:user>/<str:name>/',
        login_required(TokenDelete.as_view()),
        name='token-delete'
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
        'ucs/list/<path:token>/',
        ContentIndex.as_view(),
        name='ucontent-list'
    ),
    path(
        'ucs/export/<path:token>/',
        ContentIndex.as_view(scope="export"),
        name='ucontent-export'
    ),
    path(
        'ucs/add/<str:user>/<str:name>/<slug:type>/',
        ContentAdd.as_view(),
        name='ucontent-add'
    ),
    path(
        'ucs/add/<str:name>/<slug:type>/',
        ContentAdd.as_view(),
        name='ucontent-add'
    ),
    path(
        'content/access/<path:token>/<slug:access>/',
        ContentAccess.as_view(),
        name='ucontent-access'
    ),
    path(
        'content/remove/<slug:user>/<str:name>/<path:token>/',
        ContentRemove.as_view(),
        name='ucontent-remove'
    ),
    path(
        'ucs/',
        ComponentPublicIndex.as_view(
            is_home=False
        ),
        name='ucomponent-listpublic'
    ),
]
