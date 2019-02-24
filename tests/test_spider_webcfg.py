# import unittest

from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse
import requests

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import VariantType
from spkcspider.apps.spider.models import ContentVariant
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server
# Create your tests here.


class WebCfgTest(TransactionWebTest):
    fixtures = ['test_default.json']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.refserver = create_referrer_server(("127.0.0.1", 0))
        cls.refserver.runthread.start()

    @classmethod
    def tearDownClass(cls):
        cls.refserver.shutdown()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_webcfg(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.feature.value
        ).values_list("name", "id"))
        self.app.set_user("testuser1")

        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "token": home.token
            }
        )
        form = self.app.get(updateurl).forms["componentForm"]
        for field in form.fields["features"]:
            if field._value == str(features["WebConfig"]):
                field.checked = True
                break
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(home.features.filter(
            name="Persistence"
        ).exists())
        self.assertEqual(len(home.features.all()), 2)
        token = None
        with override_settings(DEBUG=True):
            purl = "{}?intention=persist&referrer=http://{}:{}".format(
                home.get_absolute_url(),
                *self.refserver.socket.getsockname()
            )
            response = self.app.get(purl)
            response = response.form.submit("action", value="confirm")
            query = parse_qs(urlsplit(response.location).query)
            self.assertEqual(query.get("status"), ["success"])
            self.assertIn("hash", query)
            requests.get(response.location)
            token = self.refserver.tokens[query["hash"][0]]["token"]

        # logout and clean session
        self.app.set_user(user=None)
        self.app.reset()
        webcfgurl = "{}?token={}".format(reverse(
            "spider_webcfg:webconfig-view",
        ), token)

        response = self.app.get(webcfgurl)
        self.assertEqual(response.text, "")
        response = self.app.post(webcfgurl, b"content")
        self.assertEqual(response.text, "")
        response = self.app.get(webcfgurl)
        self.assertEqual(response.text, "content")
