"""spkcspider URL Configuration

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
from spkcspider.apps.spider.views import ComponentAllIndex

favicon_view = RedirectView.as_view(
    url='{}spider_base/favicon.png'.format(settings.STATIC_URL), permanent=True
)
robots_view = RedirectView.as_view(
    url='{}spider_base/robots.txt'.format(settings.STATIC_URL), permanent=True
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/',
        include('spkcspider.apps.spider_accounts.urls', namespace="auth")
    ),
    path(
        'spider/',
        include('spkcspider.apps.spider.urls', namespace="spider_base")
    ),
]

for app_name, app_path in getattr(settings, "SPKBPIDER_APPS", {}).items():
    urlpatterns.append(
        "{}/".format(app_name),
        include("{}.urls".format(app_path), namespace=app_name)
    )

urlpatterns += [
    path('pages/', include('django.contrib.flatpages.urls')),
    path('favicon.ico', favicon_view),
    path('robots.txt', robots_view),
    path(
        '',
        ComponentAllIndex.as_view(
            is_home=True, template_name="spider_base/home.html"
        ),
        name="home"
    ),
]
try:
    import captcha  # noqa: F401
    urlpatterns.append(path(r'captcha/', include('captcha.urls')))
except ImportError:
    pass
