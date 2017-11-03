from django.conf.urls import url

from .views import BrokerIndex, BrokerAllIndex, BrokerDetail, BrokerCreate, BrokerUpdate, BrokerDelete


# bk = broker
urlpatterns = [
    url(r'^bk/(?P<user>[-\w]+)/$', BrokerIndex.as_view(), name='bk-list'),
    url(r'^bk/(?P<user>[-\w]+)/create/$', BrokerCreate.as_view(), name='bk-create'),
    url(r'^bk/(?P<user>[-\w]+)/update/(?P<id>[-\w]+)/$', BrokerUpdate.as_view(), name='bk-update'),
    url(r'^bk/(?P<user>[-\w]+)/view/(?P<id>[-\w]+)/$', BrokerDetail.as_view(), name='bk-view'),
    #url(r'^bk/(?P<user>[-\w]+)/json/(?P<id>[-\w]+)/$', BrokerJson.as_view(), name='bk-json'),
    url(r'^bk/(?P<user>[-\w]+)/delete/(?P<id>[-\w]+)/$', BrokerDelete.as_view(), name='bk-delete'),
    url(r'^bk/$', BrokerAllIndex.as_view()),

]
