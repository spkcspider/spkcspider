from django.conf.urls import url

from .views import UserComponentIndex, UserComponentAllIndex, UserComponentDetail, UserComponentCreate, UserComponentUpdate, UserComponentDelete


# uc = UserComponent
urlpatterns = [
    url(r'^(?P<user>[-\w]+)/$', UserComponentIndex.as_view(), name='uc-list'),
    url(r'^(?P<user>[-\w]+)/create/$', UserComponentCreate.as_view(), name='uc-create'),
    url(r'^(?P<user>[-\w]+)/view/(?P<name>[-\w]+)/$', UserComponentDetail.as_view(), name='uc-view'),
    url(r'^(?P<user>[-\w]+)/update/(?P<hash>[-\w]+)/$', UserComponentUpdate.as_view(), name='uc-update'),
    url(r'^(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', UserComponentDelete.as_view(), name='uc-delete'),
    url(r'^$', UserComponentAllIndex.as_view()),
]
