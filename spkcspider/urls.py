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
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.conf import settings
from django.apps import apps
from spkcspider.apps.spider.views import ComponentPublicIndex
from spkcspider.apps.spider.helpers import get_settings_func
from spkcspider.apps.spider.functions import admin_login
from django.contrib.sitemaps import views as sitemaps_views
from django.views.decorators.cache import cache_page

from spkcspider.apps.spider.sitemaps import sitemaps

favicon_view = RedirectView.as_view(
    url='{}spider_base/favicon.svg'.format(settings.STATIC_URL), permanent=True
)
robots_view = RedirectView.as_view(
    url='{}spider_base/robots.txt'.format(settings.STATIC_URL), permanent=True
)

# disable admin login page
admin.site.login = lambda *args, **kwargs: admin_login(
    admin.site, *args, **kwargs
)
# default: allow only non faked user with superuser and staff permissions
admin.site.has_permission = lambda *args, **kwargs: get_settings_func(
    "HAS_ADMIN_PERMISSION_FUNC",
    "spkcspider.apps.spider.functions.has_admin_permission"
)(admin.site, *args, **kwargs)

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
    urlpatterns.append(path(r'captcha/', include('captcha.urls')))

if 'django.contrib.flatpages' in settings.INSTALLED_APPS:
    urlpatterns.append(
        path('pages/', include('django.contrib.flatpages.urls'))
    )

urlpatterns += [
    path('favicon.ico', favicon_view),
    path('robots.txt', robots_view),
    path(
        '',
        ComponentPublicIndex.as_view(
            is_home=True, template_name="spider_base/home.html"
        ),
        name="home"
    ),
    path('sitemap.xml',
         cache_page(86400)(sitemaps_views.index),
         {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemaps'}),
    path('sitemap-<section>.xml',
         cache_page(86400)(sitemaps_views.sitemap),
         {'sitemaps': sitemaps}, name='sitemaps'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
