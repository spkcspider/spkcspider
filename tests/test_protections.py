import re
from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse


from rdflib import Graph, Literal, XSD

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.helpers import merge_get_url
from spkcspider.apps.spider.signals import update_dynamic


class ProtectionTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_login_only(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        home.public = True
        home.required_passes = 10
        home.save()
        self.assertEqual(home.strength, 4)
        # will prefer get tokens
        origurl = "?".join((home.get_absolute_url(), "token=prefer"))
        response = self.app.get(origurl).follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)
        form = response.form
        form["password"] = "abc"
        response = form.submit()
        self.assertTrue(response.location.startswith(origurl))
        self.assertIn("token=", response.location)
        self.assertNotIn("token=prefer", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

        home.public = False
        home.save()
        self.assertEqual(home.strength, 9)

        response = self.app.get(origurl).follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)
        form = response.form
        form["password"] = "abc"
        response = form.submit()
        self.assertTrue(response.location.startswith(origurl))
        self.assertIn("token=", response.location)
        self.assertNotIn("token=prefer", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

    def test_protections(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        home.protections

    def test_upgrade(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        public = self.user.usercomponent_set.filter(name="public").first()
        self.assertTrue(public)
