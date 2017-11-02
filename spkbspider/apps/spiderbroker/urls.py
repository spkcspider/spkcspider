from django.conf.urls import url

from .views import BrokerIndex, BrokerDetail, BrokerCreate, BrokerDelete

# pk = PublicKey, uc = UserComponent
urlpatterns = [
    url(r'^bk/(?P<user>[-\w]+)/$', BrokerIndex.as_view(), name='bk-list'),
    url(r'^bk/(?P<user>[-\w]+)/create/$', BrokerCreate.as_view(), name='bk-create'),
    url(r'^bk/(?P<user>[-\w]+)/view/(?P<hash>[-\w]+)/$', BrokerDetail.as_view(), name='bk-view'),
    url(r'^bk/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', BrokerDelete.as_view(), name='bk-delete'),

]
