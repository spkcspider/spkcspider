from django.conf.urls import url

from .views import PublicKeyIndex, PublicKeyDetail, PublicKeyCreate, PublicKeyUpdate, PublicKeyDelete
from .views import UserComponentIndex, UserComponentDetail, UserComponentCreate, UserComponentUpdate, UserComponentDelete

# pk = PublicKey, uc = UserComponent
urlpatterns = [
    url(r'^pk/(?P<user>[-\w]+)/list/$', PublicKeyIndex.as_view(), name='pk-list'),
    url(r'^pk/(?P<user>[-\w]+)/create/$', PublicKeyCreate.as_view(), name='pk-create'),
    url(r'^pk/(?P<user>[-\w]+)/view/(?P<hash>[-\w]+)/$', PublicKeyDetail.as_view(), name='pk-view'),
    url(r'^pk/(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', PublicKeyUpdate.as_view(), name='pk-update'),
    url(r'^pk/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', PublicKeyDelete.as_view(), name='pk-delete'),

    url(r'^uc/(?P<user>[-\w]+)/list/$', UserComponentIndex.as_view(), name='uc-list'),
    url(r'^uc/(?P<user>[-\w]+)/create/$', UserComponentCreate.as_view(), name='uc-create'),
    url(r'^uc/(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/$', UserComponentDetail.as_view(), name='uc-view'),
    url(r'^uc/(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', UserComponentUpdate.as_view(), name='uc-update'),
    url(r'^uc/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', UserComponentDelete.as_view(), name='uc-delete'),
]
