from django.conf.urls import url

from .views import RedirectUserPK, RedirectUserUC
from .views import PublicKeyIndex, PublicKeyAllIndex, PublicKeyDetail, PublicKeyCreate, PublicKeyUpdate, PublicKeyDelete
from .views import UserComponentIndex, UserComponentAllIndex, UserComponentDetail, UserComponentCreate, UserComponentUpdate, UserComponentDelete


# pk = PublicKey, uc = UserComponent
urlpatterns = [
    url(r'^pk/(?P<user>[-\w]+)/$', PublicKeyIndex.as_view(), name='pk-list'),
    url(r'^pk/(?P<user>[-\w]+)/create/$', PublicKeyCreate.as_view(), name='pk-create'),
    url(r'^pk/(?P<user>[-\w]+)/view/(?P<hash>[-\w]+)/$', PublicKeyDetail.as_view(), name='pk-view'),
    url(r'^pk/(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', PublicKeyUpdate.as_view(), name='pk-update'),
    url(r'^pk/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', PublicKeyDelete.as_view(), name='pk-delete'),
    url(r'^pk/$', PublicKeyAllIndex.as_view()),

    url(r'^uc/(?P<user>[-\w]+)/$', UserComponentIndex.as_view(), name='uc-list'),
    url(r'^uc/(?P<user>[-\w]+)/create/$', UserComponentCreate.as_view(), name='uc-create'),
    url(r'^uc/(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/$', UserComponentDetail.as_view(), name='uc-view'),
    url(r'^uc/(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', UserComponentUpdate.as_view(), name='uc-update'),
    url(r'^uc/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', UserComponentDelete.as_view(), name='uc-delete'),
    url(r'^uc/$', UserComponentAllIndex.as_view()),
]
