from django.conf.urls import url

from .views import PublicKeyIndex, PublicKeyAllIndex, PublicKeyDetail, PublicKeyCreate, PublicKeyUpdate, PublicKeyDelete


# pk = PublicKey, uc = UserComponent
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', PublicKeyIndex.as_view(), name='pk-list'),
    url(r'^(?P<user>[-\w]+)/create/$', PublicKeyCreate.as_view(), name='pk-create'),
    url(r'^(?P<user>[-\w]+)/view/(?P<hash>[-\w]+)/$', PublicKeyDetail.as_view(), name='pk-view'),
    url(r'^(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', PublicKeyUpdate.as_view(), name='pk-update'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', PublicKeyDelete.as_view(), name='pk-delete'),
    url(r'^$', PublicKeyAllIndex.as_view()),
]
