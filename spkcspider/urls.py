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
from django.contrib.auth.decorators import login_required
from django.apps import apps
from spkcspider.apps.spider.views import ComponentAllIndex

favicon_view = RedirectView.as_view(
    url='{}spider_base/favicon.svg'.format(settings.STATIC_URL), permanent=True
)
robots_view = RedirectView.as_view(
    url='{}spider_base/robots.txt'.format(settings.STATIC_URL), permanent=True
)

# disable admin login page
admin.site.login = login_required(admin.site.login)
urlpatterns = [
    path('admin/', admin.site.urls),
]

for app in apps.get_app_configs():
    url_namespace = getattr(app, "url_namespace", None)
    if url_namespace:
        url_path = getattr(
            app, "url_path",
            url_namespace.replace("spider_", "")+"/"
        )
        urlpatterns.append(
            path(
                url_path,
                include("{}.urls".format(app.name), namespace=url_namespace)
            )
        )


if getattr(settings, "USE_CAPTCHAS", False):
    urlpatterns.apppend(path(r'captcha/', include('captcha.urls')))

if 'django.contrib.flatpages' in settings.INSTALLED_APPS:
    urlpatterns.append(
        path('pages/', include('django.contrib.flatpages.urls'))
    )

urlpatterns += [
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
