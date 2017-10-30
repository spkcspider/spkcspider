from django.conf.urls import url

from .views import BrokerIndex, BrokerDetail, BrokerCreate, BrokerDelete

urlpatterns = [
    url(r'^broker/(?P<user>[-\w]+)/$', BrokerIndex.as_view(), name='broker-list'),
    url(r'^broker/(?P<user>[-\w]+)/create/$', BrokerCreate.as_view(), name='broker-create'),
    url(r'^broker/(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/$', BrokerDetail.as_view(), name='broker-view'),
    url(r'^broker/(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', BrokerUpdate.as_view(), name='broker-update'),
    url(r'^broker/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', BrokerDelete.as_view(), name='broker-delete'),
]
