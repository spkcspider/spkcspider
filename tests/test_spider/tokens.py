
from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse
import requests

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants import VariantType
from spkcspider.apps.spider.models import (
    ContentVariant, AuthToken, ReverseToken
)
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server
# Create your tests here.


class TokenTest(TransactionWebTest):
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

    def test_reverse_token(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        self.app.set_user("testuser1")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorServer"
            }
        )
        form = self.app.get(createurl).forms[0]
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(home.contents.count(), 1)
        content = home.contents.first()
        ntoken = "abcdefg"
        e = ReverseToken.objects.create(assignedcontent=content)
        url = reverse("spider_base:reverse-token")
        self.app.post(
            url, {
                "payload": "{},{}".format(
                    content.token, e.id
                ), "token": ntoken
            }
        )
        e.refresh_from_db()
        self.assertEqual(e.token, ntoken)

    def test_renew_post(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.component_feature.value
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
            if field._value == str(features["Persistence"]):
                field.checked = True
        response = form.submit()
        self.assertEqual(response.status_code, 200)

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
            token = AuthToken.objects.get(
                token=self.refserver.tokens[query["hash"][0]]["token"]
            )

        # logout and clean session
        self.app.set_user(user=None)
        self.app.reset()

        oldtoken = token.token
        self.app.post(
            reverse("spider_base:token-renew"),
            {"token": token.token}
        )
        token.refresh_from_db()
        self.assertNotEqual(oldtoken, token.token)

    def test_renew_sl(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.component_feature.value
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
            if field._value == str(features["Persistence"]):
                field.checked = True
        response = form.submit()
        self.assertEqual(response.status_code, 200)

        token = None
        with override_settings(DEBUG=True):
            purl = "{}?intention=persist&intention=sl&referrer=http://{}:{}".format(  # noqa: E501
                home.get_absolute_url(),
                *self.refserver.socket.getsockname()
            )
            response = self.app.get(purl)
            response = response.form.submit("action", value="confirm")
            query = parse_qs(urlsplit(response.location).query)
            requests.get(response.location)
            token = AuthToken.objects.get(
                token=query["token"][0]
            )

        # logout and clean session
        self.app.set_user(user=None)
        self.app.reset()

        newtoken = self.app.post(
            reverse("spider_base:token-renew"),
            {"token": token.token},
            headers={
                "Referer": token.referrer.url
            }
        ).text

        oldtoken = token.token
        token.refresh_from_db()
        self.assertNotEqual(oldtoken, token.token)
        self.assertEqual(newtoken, token.token)