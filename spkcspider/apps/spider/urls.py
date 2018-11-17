from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page

from .views import (
    ComponentIndex, ComponentPublicIndex, ComponentCreate,
    ComponentUpdate, ComponentDelete
)
from .views import (
    ContentAdd, ContentIndex, ContentAccess, ContentRemove
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
        'ucs/update/<slug:user>/<str:name>/<slug:nonce>/',
        login_required(ComponentUpdate.as_view()),
        name='ucomponent-update'
    ),
    path(
        'ucs/update/<str:name>/<slug:nonce>/',
        login_required(ComponentUpdate.as_view()),
        name='ucomponent-update'
    ),
    path(
        'ucs/delete/<slug:user>/<str:name>/<slug:nonce>/',
        login_required(ComponentDelete.as_view()),
        name='ucomponent-delete'
    ),

    path(
        'ucs/list/<int:id>/<slug:nonce>/',
        cache_page(120)(ContentIndex.as_view()),
        name='ucontent-list'
    ),
    path(
        'ucs/export/<int:id>/<slug:nonce>/',
        login_required(ContentIndex.as_view(scope="export")),
        name='ucontent-export'
    ),
    # path(
    #     'ucs/add/<slug:user>/<slug:name>/<slug:type>/',
    #     ContentAdd.as_view(),
    #     name='ucontent-add'
    # ),
    path(
        'ucs/add/<str:name>/<slug:type>/',
        login_required(ContentAdd.as_view()),
        name='ucontent-add'
    ),
    path(
        'content/access/<int:id>/<slug:nonce>/<slug:access>/',
        ContentAccess.as_view(),
        name='ucontent-access'
    ),
    path(
        'content/remove/<slug:user>/<str:name>/<int:id>/<slug:nonce>/',
        login_required(ContentRemove.as_view()),
        name='ucontent-remove'
    ),
    path(
        'ucs/',
        ComponentPublicIndex.as_view(is_home=False),
        name='ucomponent-listpublic'
    ),
]
