from django.urls import path

from .views import (
    ComponentIndex, ComponentAllIndex, ComponentCreate,
    ComponentUpdate, ComponentDelete
)
from .views import (
    ContentView, ContentIndex, ContentAdd, ContentUpdate, ContentRemove
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
        'ucs/delete/<slug:name>/',
        ComponentDelete.as_view(),
        name='ucomponent-delete'
    ),

    path(
        'ucs/list/<slug:user>/<slug:name>/',
        ContentIndex.as_view(),
        name='ucontent-list'
    ),
    path(
        'ucs/list/<slug:name>/',
        ContentIndex.as_view(),
        name='ucontent-list'
    ),
    path(
        'ucs/add/<slug:type>/<slug:name>/',
        ContentAdd.as_view(),
        name='ucontent-add'
    ),

    path(
        'content/view/<int:id>/',
        ContentView.as_view(raw=False),
        name='ucontent-view'
    ),
    path(
        'content/view/<int:id>/raw/',
        ContentView.as_view(raw=True),
        name='ucontent-raw-view'
    ),
    path(
        'content/update/<int:id>/',
        ContentUpdate.as_view(),
        name='ucontent-update'
    ),
    path(
        'content/remove/<int:id>/',
        ContentRemove.as_view(),
        name='ucontent-remove'
    ),
    path(
        'ucs/',
        ComponentAllIndex.as_view(is_home=False),
        name='ucomponent-listall'
    ),
]
