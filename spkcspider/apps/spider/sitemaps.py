__all__ = ["sitemaps", "ComponentSitemap", "ContentSitemap", "HomeSitemap"]

from django.contrib.sitemaps import GenericSitemap, Sitemap
from django.urls import reverse
from django.conf import settings


class ComponentSitemap(GenericSitemap):
    priority = 0.3
    changefreq = "daily"
    date_field = "modified"
    if not settings.DEBUG:
        protocol = "https"

    def __init__(self):
        from .models import UserComponent
        self.queryset = UserComponent.objects.filter(
            public=True
        )


class ContentSitemap(GenericSitemap):
    priority = 0.7
    changefreq = "hourly"
    date_field = "modified"
    if not settings.DEBUG:
        protocol = "https"

    def __init__(self):
        from .models import AssignedContent
        self.queryset = AssignedContent.objects.filter(
            usercomponent__public=True
        ).exclude(info__contains="_unlisted")


class HomeSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'
    if not settings.DEBUG:
        protocol = "https"

    def items(self):
        return ['home']

    def location(self, item):
        return reverse(item)


sitemaps = {
    'components': ComponentSitemap,
    'contents': ContentSitemap,
    'home': HomeSitemap
}
