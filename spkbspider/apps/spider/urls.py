from django.urls import path

from .views import ComponentIndex, ComponentAllIndex, ComponentCreate, ComponentUpdate, ComponentDelete, ComponentResetDelete
from .views import ContentView, ContentIndex, ContentAdd, ContentUpdate, ContentRemove, ContentResetRemove

app_name = "spiderucs"

# uc = UserComponent
urlpatterns = [
    path('<slug:user>/index/', ComponentIndex.as_view(), name='ucomponent-list'),
    path('<slug:user>/create/', ComponentCreate.as_view(), name='ucomponent-create'),
    path('<slug:user>/update/<slug:name>/', ComponentUpdate.as_view(), name='ucomponent-update'),
    path('<slug:user>/delete-reset/<slug:name>/', ComponentResetDelete.as_view(), name='ucomponent-resetdelete'),
    path('<slug:user>/delete/<slug:name>/', ComponentDelete.as_view(), name='ucomponent-delete'),

    path('<slug:user>/list/<slug:name>/', ContentIndex.as_view(), name='ucontent-list'),
    path('<slug:user>/view/<slug:name>/<int:id>/', ContentView.as_view(), name='ucontent-view'),
    path('<slug:user>/add/<slug:name>/<slug:type>/', ContentAdd.as_view(), name='ucontent-add'),
    path('<slug:user>/cupdate/<slug:name>/<int:id>/', ContentUpdate.as_view(), name='ucontent-update'),
    path('<slug:user>/remove-reset/<slug:name>/<int:id>/', ContentResetRemove.as_view(), name='ucontent-resetremove'),
    path('<slug:user>/remove/<slug:name>/<int:id>/', ContentRemove.as_view(), name='ucontent-remove'),
    path('', ComponentAllIndex.as_view()),
]
