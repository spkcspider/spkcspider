from django.conf.urls import url

from .views import PublicKeyIndex, PublicKeyView, PublicKeyCreate, PublicKeyUpdate, PublicKeyDelete
from .views import UserComponentIndex, UserComponentView, UserComponentCreate, UserComponentUpdate, UserComponentDelete


urlpatterns = [
    url(r'^(?P<slug>[-\w]+)/$', ArticleDetailView.as_view(), name='article-detail'),
]
