"""spkbspider URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.conf import settings


favicon_view = RedirectView.as_view(url='{}spkbspider/favicon.png'.format(settings.STATIC_URL), permanent=True)
robots_view = RedirectView.as_view(url='{}spkbspider/robots.txt'.format(settings.STATIC_URL), permanent=True)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include('spkbspider.apps.spideraccounts.urls', namespace="auth")),
    url(r'^comps/', include('spkbspider.apps.spiderpk.urls', namespace="spiderpk")),
    url(r'^brokers/', include('spkbspider.apps.spiderbroker.urls', namespace="spiderbroker")),
    url(r'^pages/', include('django.contrib.flatpages.urls')),
    #url(r'^favicon\.ico$', favicon_view),
    #url(r'^robots\.txt$', robots_view),

]
