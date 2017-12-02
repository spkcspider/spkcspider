from django.conf.urls import url

from .views import PublicKeyIndex, PublicKeyAllIndex, PublicKeyDetail, PublicKeyCreate, PublicKeyUpdate, PublicKeyDelete


# pk = PublicKey, uc = UserComponent
urlpatterns = [
    url(r'^index/(?P<user>[-\w]+)/$', PublicKeyIndex.as_view(), name='pk-list'),
    url(r'^create/$', PublicKeyCreate.as_view(), name='pk-create'),
    url(r'^view/(?P<hash>[-\w]+)/$', PublicKeyDetail.as_view(), name='pk-view'),
    url(r'^update/(?P<hash>[-\w]+)/$', PublicKeyUpdate.as_view(), name='pk-update'),
    url(r'^delete/(?P<hash>[-\w]+)/$', PublicKeyDelete.as_view(), name='pk-delete'),
    url(r'^index/$', PublicKeyAllIndex.as_view()),
]
