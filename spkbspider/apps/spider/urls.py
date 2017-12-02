from django.conf.urls import url

from .views import UserComponentIndex, UserComponentAllIndex, UserComponentCreate, UserComponentUpdate, UserComponentDelete


# uc = UserComponent
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', UserComponentIndex.as_view(), name='ucomponent-list'),
    url(r'^(?P<user>[-\w]+)/create/$', UserComponentCreate.as_view(), name='ucomponent-create'),
    url(r'^(?P<user>[-\w]+)/update/(?P<name>[-\w]+)/$', UserComponentUpdate.as_view(), name='ucomponent-update'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<name>[-\w]+)/$', UserComponentDelete.as_view(), name='ucomponent-delete'),

    #url(r'^(?P<user>[-\w]+)/list/(?P<name>[-\w]+)/$', ContentIndex.as_view(), name='ucontent-list'),
    #url(r'^(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentView.as_view(), name='ucontent-view'),
    #url(r'^(?P<user>[-\w]+)/add/(?P<name>[-\w]+)/(?P<type>[-\w]+)$', ContentCreate.as_view(), name='ucontent-create'),
    #url(r'^(?P<user>[-\w]+)/cupdate/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentUpdate.as_view(), name='ucontent-update'),
    #url(r'^(?P<user>[-\w]+)/remove/(?P<name>[-\w]+)/(?P<id>[0-9]+)/$', ContentDelete.as_view(), name='ucontent-delete'),
    url(r'^$', UserComponentAllIndex.as_view()),
]
