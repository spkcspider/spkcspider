from django.conf.urls import url
from django.urls import reverse

from django.views.generic.base import RedirectView
from .views import BrokerIndex, BrokerDetail, BrokerCreate, BrokerDelete

class RedirectUser(RedirectView):
    permanent = True
    def get_success_url(self):
        return reverse("broker:bk-list", user=request.user)

# bk = broker
urlpatterns = [
    url(r'^bk/(?P<user>[-\w]+)/list/$', BrokerIndex.as_view(), name='bk-list'),
    url(r'^bk/(?P<user>[-\w]+)/create/$', BrokerCreate.as_view(), name='bk-create'),
    url(r'^bk/(?P<user>[-\w]+)/view/(?P<hash>[-\w]+)/$', BrokerDetail.as_view(), name='bk-view'),
    url(r'^bk/(?P<user>[-\w]+)/delete/(?P<hash>[-\w]+)/$', BrokerDelete.as_view(), name='bk-delete'),
    url(r'^bk/$', RedirectUser.as_view()),

]
