# import unittest

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
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server
# Create your tests here.


class FeaturesTest(TransactionWebTest):
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

    def test_update_perm(self):
        home = self.user.usercomponent_set.filter(name="home").first()

        with self.subTest(msg="Auth Protections inactive"):
            purl = "{}?intention=auth".format(
                home.get_absolute_url()
            )
            response = self.app.get(purl)
            # check redirect
            self.assertEqual(response.status_code, 302)
            target = "{}?next=".format(reverse("auth:login"))
            self.assertTrue(response.location.startswith(target))
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "name": "home",
                "user": "testuser1",
                "nonce": home.nonce
            }
        )
        self.app.set_user(user="testuser1")
        form = self.app.get(updateurl).forms["componentForm"]
        form.set("public", False)
        form.set("protections_login-active", True)
        form.set("protections_login-allow_auth", True)
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(home.protections.all().count(), 1)
        self.assertEqual(home.strength, 5)
        # logout and clean session
        # deleting form required
        del response
        del form
        self.app.set_user(user=None)
        self.app.reset()
        # set pw
        self.user.set_password("abc")
        self.user.save()

        with self.subTest(msg="Auth Protections active"):
            purl = "{}?intention=auth&token=prefer".format(
                home.get_absolute_url()
            )
            response = self.app.get(purl)
            self.assertEqual(response.status_code, 200)
            form = response.forms[0]
            form["password"] = "abc"
            response = form.submit()
            # response.showbrowser()
            location = response.location
            response = response.follow()
            self.assertEqual(response.status_code, 200)
            self.assertIn("token=", location)
            self.assertTrue(response.html.find(
                "details"
            ))

    def test_persistent(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.feature.value
        ).values_list("name", "id"))
        self.app.set_user("testuser1")

        with self.subTest(msg="Persist inactive"):
            with override_settings(DEBUG=True):
                purl = "{}?intention=persist&referrer=http://{}:{}".format(
                    home.get_absolute_url(),
                    *self.refserver.socket.getsockname()
                )
                response = self.app.get(purl, expect_errors=True, status=400)
                # invalid so check that error
                self.assertEqual(response.status_code, 400)

        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "name": "home",
                "nonce": home.nonce
            }
        )
        form = self.app.get(updateurl).forms["componentForm"]
        for i in range(0, len(features)):
            field = form.get("features", index=i)
            if field._value == str(features["WebConfig"]):
                field.checked = True
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(home.features.filter(
            name="Persistence"
        ).exists())
        self.assertEqual(len(home.features.all()), 2)
        # now test persistence feature
        with self.subTest(msg="Persist"):
            with override_settings(DEBUG=True):
                purl = "{}?intention=persist".format(
                    home.get_absolute_url()
                )
                response = self.app.get(purl)

                # invalid so check that no update
                self.assertTrue("Content" in str(response.html.title))
                purl = "{}?intention=persist&referrer=http://{}:{}".format(
                    home.get_absolute_url(),
                    *self.refserver.socket.getsockname()
                )
                response = self.app.get(purl)
                g = Graph()
                g.parse(data=str(response.content, "utf8"), format="html")
                self.assertIn(
                    (None, None, Literal("Persistence", datatype=XSD.string)),
                    g
                )
                self.assertIn(
                    (None, None, Literal("WebConfig", datatype=XSD.string)),
                    g
                )
                self.assertTrue(response.html.find(
                    "button", attrs={"value": ""},
                    string=re.compile("Refresh")
                ))
                self.assertTrue(response.html.find(
                    "button", attrs={"value": "confirm"},
                    string=re.compile("Confirm")
                ))

                self.assertTrue(response.html.find(
                    "button", attrs={"value": "cancel"},
                    string=re.compile("Cancel")
                ))

                response = response.forms[0].submit("action", value="confirm")
                query = parse_qs(urlsplit(response.location).query)
                self.assertIn("hash", query)
                self.assertEqual(query.get("status"), ["success"])
                self.assertIn(query["hash"][0], self.refserver.unverified)
                requests.get(response.location)
                self.assertIn(query["hash"][0], self.refserver.tokens)
