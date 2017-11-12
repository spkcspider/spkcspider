from django.conf.urls import url

from .views import BrokerIndex, BrokerAllIndex, BrokerDetail, BrokerCreate, BrokerUpdate, BrokerDelete


# bk = broker
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', BrokerIndex.as_view(), name='bk-list'),
    url(r'^(?P<user>[-\w]+)/create/$', BrokerCreate.as_view(), name='bk-create'),
    url(r'^(?P<user>[-\w]+)/update/(?P<id>[0-9]+)/$', BrokerUpdate.as_view(), name='bk-update'),
    url(r'^(?P<user>[-\w]+)/view/(?P<id>[0-9]+)/$', BrokerDetail.as_view(), name='bk-view'),
    #url(r'^bk/(?P<user>[-\w]+)/json/(?P<id>[-\w]+)/$', BrokerJson.as_view(), name='bk-json'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<id>[0-9]+)/$', BrokerDelete.as_view(), name='bk-delete'),
    url(r'^$', BrokerAllIndex.as_view()),

]
