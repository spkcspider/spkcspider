"""spkbspider URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.conf import settings
from spkbspider.apps.spider.views import ComponentAllIndex

favicon_view = RedirectView.as_view(url='{}spkbspider/favicon.png'.format(settings.STATIC_URL), permanent=True)
robots_view = RedirectView.as_view(url='{}spkbspider/robots.txt'.format(settings.STATIC_URL), permanent=True)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('spkbspider.apps.spideraccounts.urls', namespace="auth")),
    path('ucs/', include('spkbspider.apps.spider.urls', namespace="spiderucs")),
]

for app_name, app_path in getattr(settings, "SPKBPIDER_APPS", {}).items():
    urlpatterns.append("{}/".format(app_name), include("{}.urls".format(app_path), namespace=app_name))

urlpatterns += [
    path('pages/', include('django.contrib.flatpages.urls')),
    path('favicon.ico', favicon_view),
    path('robots.txt', robots_view),
    path('', ComponentAllIndex.as_view(is_home=True, template_name="spkbspider/home.html"), name="home"),
]
