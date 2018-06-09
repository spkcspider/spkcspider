from django.urls import path

from .views import (
    ComponentIndex, ComponentAllIndex, ComponentCreate,
    ComponentUpdate, ComponentDelete
)
from .views import (
    ContentAdd, ContentIndex, ContentAccess, ContentRemove
)

app_name = "spider_base"

# uc = UserComponent
urlpatterns = [
    path(
        'ucs/user/<slug:user>/',
        ComponentIndex.as_view(),
        name='ucomponent-list'
    ),
    path('ucs/user/', ComponentIndex.as_view(), name='ucomponent-list'),
    path('ucs/create/', ComponentCreate.as_view(), name='ucomponent-create'),
    path(
        'ucs/update/<slug:name>/',
        ComponentUpdate.as_view(),
        name='ucomponent-update'
    ),
    path(
        'ucs/delete/<slug:name>/<slug:nonce>/',
        ComponentDelete.as_view(),
        name='ucomponent-delete'
    ),

    path(
        'ucs/list/<slug:user>/<slug:name>/<slug:nonce>/',
        ContentIndex.as_view(),
        name='ucontent-list'
    ),
    path(
        'ucs/add/<slug:user>/<slug:name>/<slug:type>/',
        ContentAdd.as_view(),
        name='ucontent-add'
    ),
    path(
        'content/access/<int:id>/<slug:nonce>/<slug:access>/',
        ContentAccess.as_view(),
        name='ucontent-access'
    ),
    path(
        'content/remove/<slug:user>/<slug:name>/<int:id>/<slug:nonce>/',
        ContentRemove.as_view(),
        name='ucontent-remove'
    ),
    path(
        'ucs/',
        ComponentAllIndex.as_view(is_home=False),
        name='ucomponent-listall'
    ),
]
