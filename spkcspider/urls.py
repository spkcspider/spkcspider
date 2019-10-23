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

from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps import views as sitemaps_views
from django.urls import include, path
from django.views.decorators.cache import cache_page
from django.views.generic.base import RedirectView
from spkcspider.apps.spider.functions import admin_login
from spkcspider.apps.spider.sitemaps import sitemaps
from spkcspider.apps.spider.views import ComponentPublicIndex
from spkcspider.utils.settings import get_settings_func

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
    path(
        '',
        ComponentPublicIndex.as_view(
            is_home=True, template_name="spider_base/home.html"
        ),
        name="home"
    ),
    path('i18n/', include('django.conf.urls.i18n'))
]

for app in apps.get_app_configs():
    url_path = getattr(
        app, "spider_url_path",
        None
    )
    if not url_path:
        continue
    urlpatterns.append(
        path(
            url_path,
            include("{}.urls".format(app.name))
        )
    )


if getattr(settings, "SPIDER_LEGACY_REDIRECT", False):
    urlpatterns.insert(
        0,
        path(
            'spider/content/<int:token1>/<str:token2>/<slug:access>/',
            RedirectView.as_view(
                url='/spider/content/%(token1)s_%(token2)s/%(access)s/',
                permanent=True
            )
        )
    )
    urlpatterns.insert(
        0,
        path(
            'spider/components/<int:token1>/<str:token2>/list/',
            RedirectView.as_view(
                url='/spider/components/%(token1)s_%(token2)s/list/',
                permanent=True
            )
        )
    )
    urlpatterns.insert(
        0,
        path(
            'spider/content/access/<int:token1>/<str:token2>/<slug:access>/',
            RedirectView.as_view(
                url='/spider/content/%(token1)s_%(token2)s/%(access)s/',
                permanent=True
            )
        )
    )
    urlpatterns.insert(
        0,
        path(
            'spider/ucs/list/<int:token1>/<str:token2>/',
            RedirectView.as_view(
                url='/components/%(token1)s_%(token2)s/list/',
                permanent=True
            )
        )
    )


if getattr(settings, "USE_CAPTCHAS", False):
    urlpatterns.append(path(r'captcha/', include('captcha.urls')))

if 'django.contrib.flatpages' in settings.INSTALLED_APPS:
    urlpatterns.append(
        path('pages/', include('django.contrib.flatpages.urls'))
    )

urlpatterns += [
    # daily
    path('favicon.ico', cache_page(86400)(favicon_view)),
    path('robots.txt', cache_page(86400)(robots_view)),
    # daily
    path(
        'sitemap.xml',
        cache_page(86400)(
            sitemaps_views.index
        ),
        {
            'sitemaps': sitemaps,
            'sitemap_url_name': 'sitemaps'
        },
        name='django.contrib.sitemaps.views.index'
    ),
    # hourly
    path(
        'sitemap-<section>.xml',
        cache_page(3600)(
            sitemaps_views.sitemap
        ),
        {'sitemaps': sitemaps},
        name='sitemaps'
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
