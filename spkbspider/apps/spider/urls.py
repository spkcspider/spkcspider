from django.conf.urls import url

from .views import UserComponentIndex, UserComponentAllIndex, UserComponentDetail, UserComponentCreate, UserComponentUpdate, UserComponentDelete


# uc = UserComponent
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', UserComponentIndex.as_view(), name='uc-list'),
    url(r'^(?P<user>[-\w]+)/create/$', UserComponentCreate.as_view(), name='uc-create'),
    url(r'^(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/$', UserComponentDetail.as_view(), name='uc-view'),
    url(r'^(?P<user>[-\w]+)/update/(?P<name>[-\w]+)/$', UserComponentUpdate.as_view(), name='uc-update'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<name>[-\w]+)/$', UserComponentDelete.as_view(), name='uc-delete'),
    # don't expose name
    #url(r'^(?P<user>[-\w]+)/protections/(?P<ucid>[0-9]+)/$', ProtectionListView.as_view(), name='uc-protections'),
    #url(r'^(?P<user>[-\w]+)/protection/(?P<ucid>[0-9]+)/(?P<pname>[-\w]+)/$', ProtectionView.as_view(), name='protection'),
    url(r'^$', UserComponentAllIndex.as_view()),
]
