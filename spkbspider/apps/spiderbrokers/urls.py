from django.conf.urls import url

from .views import BrokerIndex, BrokerAllIndex, BrokerDetail, BrokerCreate, BrokerUpdate, BrokerDelete


# bk = broker
urlpatterns = [
    url(r'^index/(?P<user>[-\w]+)/$', BrokerIndex.as_view(), name='bk-list'),
    url(r'^create/$', BrokerCreate.as_view(), name='bk-create'),
    url(r'^update/(?P<id>[0-9]+)/$', BrokerUpdate.as_view(), name='bk-update'),
    url(r'^view/(?P<id>[0-9]+)/$', BrokerDetail.as_view(), name='bk-view'),
    #url(r'^bk/(?P<user>[-\w]+)/json/(?P<id>[-\w]+)/$', BrokerJson.as_view(), name='bk-json'),
    url(r'^delete/(?P<id>[0-9]+)/$', BrokerDelete.as_view(), name='bk-delete'),
    url(r'^index/$', BrokerAllIndex.as_view()),

]
