from django.conf.urls import url

from .views import ComponentIndex, ComponentAllIndex, ComponentCreate, ComponentUpdate, ComponentDelete
from .views import ContentView, ContentIndex, ContentAdd, ContentUpdate, ContentRemove, ContentResetRemove


# uc = UserComponent
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', ComponentIndex.as_view(), name='ucomponent-list'),
    url(r'^(?P<user>[-\w]+)/create/$', ComponentCreate.as_view(), name='ucomponent-create'),
    url(r'^(?P<user>[-\w]+)/update/(?P<name>[-\w]+)/$', ComponentUpdate.as_view(), name='ucomponent-update'),
    url(r'^(?P<user>[-\w]+)/delete-reset/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentResetRemove.as_view(), name='ucontent-resetdelete'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<name>[-\w]+)/$', ComponentDelete.as_view(), name='ucomponent-delete'),

    url(r'^(?P<user>[-\w]+)/list/(?P<name>[-\w]+)/$', ContentIndex.as_view(), name='ucontent-list'),
    url(r'^(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentView.as_view(), name='ucontent-view'),
    url(r'^(?P<user>[-\w]+)/add/(?P<name>[-\w]+)/(?P<type>[_\w]+)$', ContentCreate.as_view(), name='ucontent-add'),
    url(r'^(?P<user>[-\w]+)/cupdate/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentUpdate.as_view(), name='ucontent-update'),
    url(r'^(?P<user>[-\w]+)/remove-reset/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentResetRemove.as_view(), name='ucontent-resetremove'),
    url(r'^(?P<user>[-\w]+)/remove/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentRemove.as_view(), name='ucontent-remove'),
    url(r'^$', ComponentAllIndex.as_view()),
]
