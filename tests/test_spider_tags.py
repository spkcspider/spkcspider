
import re
from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse
import requests
from rdflib import Graph, Literal, XSD

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import VariantType
from spkcspider.apps.spider.models import ContentVariant
from spkcspider.apps.spider_tags.models import TagLayout
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server
# Create your tests here.


class TagTest(TransactionWebTest):
    fixtures = ['test_default.json']

    @classmethod
    def setUpClass(cls):
        cls.refserver = create_referrer_server(("127.0.0.1", 0))
        cls.refserver.runthread.start()

    @classmethod
    def tearDownClass(cls):
        cls.refserver.shutdown()

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_tags(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        self.app.set_user(user="testuser1")
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "SpiderTag"
            }
        )
        response = self.app.get(createurl)
        form = response.form
        form["layout"].value = TagLayout.objects.get(name="address").pk
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        form = response.form
        form["tag/name"] = "Alouis Alchemie AG"
        form["tag/place"] = "Holdenstreet"
        form["tag/street_number"] = "40C"
        form["tag/city"] = "Liquid-City"
        form["tag/post_code"] = "123456"
        form["tag/country_code"] = "de"
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        form = response.form
        form["tag/country_code"] = "dedsdlsdlsd"
        response = form.submit()
        form = response.form
        self.assertEqual(form["tag/country_code"].value, "dedsdlsdlsd")
        print("{}?".format(
            home.contents.first().get_absolute_url("update")
        ))
        response = response.click(
            href="{}\\?".format(
                home.contents.first().get_absolute_url("view")
            ), index=0
        )
        self.assertEqual(response.status_code, 200)
        response = response.click(
            href="{}\\?".format(
                home.contents.first().get_absolute_url("update")
            )
        )
        form = response.form
        self.assertEqual(form["tag/country_code"].value, "de")
