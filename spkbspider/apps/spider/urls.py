from django.urls import path

from .views import ComponentIndex, ComponentAllIndex, ComponentCreate, ComponentUpdate, ComponentDelete, ComponentResetDelete
from .views import ContentView, ContentIndex, ContentAdd, ContentUpdate, ContentRemove, ContentResetRemove

app_name = "spiderucs"

# uc = UserComponent
urlpatterns = [
    path('ucs/<slug:user>/index/', ComponentIndex.as_view(), name='ucomponent-list'),
    path('ucs/<slug:user>/create/', ComponentCreate.as_view(), name='ucomponent-create'),
    path('ucs/<slug:user>/update/<slug:name>/', ComponentUpdate.as_view(), name='ucomponent-update'),
    path('ucs/<slug:user>/delete-reset/<slug:name>/', ComponentResetDelete.as_view(), name='ucomponent-resetdelete'),
    path('ucs/<slug:user>/delete/<slug:name>/', ComponentDelete.as_view(), name='ucomponent-delete'),

    path('ucs/<slug:user/list/<slug:name>/', ContentIndex.as_view(), name='ucontent-list'),
    path('ucs/<slug:user>/add/<slug:name>/<slug:type>/', ContentAdd.as_view(),

    path('content/view/<int:id>/', ContentView.as_view(), name='ucontent-view'), name='ucontent-add'),
    path('content/update/<int:id>/', ContentUpdate.as_view(), name='ucontent-update'),
    path('content/remove-reset/<int:id>/', ContentResetRemove.as_view(), name='ucontent-resetremove'),
    path('content/remove/<int:id>/', ContentRemove.as_view(), name='ucontent-remove'),
    path('ucs/', ComponentAllIndex.as_view(is_home=False)),
]
