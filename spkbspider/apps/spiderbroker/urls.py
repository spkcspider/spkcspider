from django.conf.urls import url

from .views import BrokerIndex, BrokerView, BrokerCreate, BrokerDelete

urlpatterns = [
    url(r'^(?P<slug>[-\w]+)/$', ArticleDetailView.as_view(), name='article-detail'),
]
