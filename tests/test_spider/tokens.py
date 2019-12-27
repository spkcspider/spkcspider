
from urllib.parse import parse_qs, urlsplit
import json
import requests

from django.test import override_settings
from django.urls import reverse
from django_webtest import TransactionWebTest
from spkcspider.apps.spider.models import AuthToken, ContentVariant
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.constants import VariantType
from tests.referrerserver import create_referrer_server


class RemoteTokenTest(TransactionWebTest):
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
        update_dynamic.send(self)

    def test_renew_post(self):
        home = self.user.usercomponent_set.get(name="home")
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.component_feature
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
            response = response.forms["SPKCReferringForm"].submit(
                "action", value="confirm"
            )
            query = parse_qs(urlsplit(response.location).query)
            self.assertEqual(query.get("status"), ["success"])
            self.assertIn("hash", query)
            requests.get(response.location, headers={"Connection": "close"})
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
        home = self.user.usercomponent_set.get(name="home")
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.component_feature
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
            response = response.forms["SPKCReferringForm"].submit(
                "action", value="confirm"
            )
            query = parse_qs(urlsplit(response.location).query)
            requests.get(response.location, headers={"Connection": "close"})
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


class OwnerTokenManagementTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        update_dynamic.send(self)
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        self.app.set_user(user="testuser1")
        self.home = self.user.usercomponent_set.get(name="home")
        self.deleteurl = reverse(
            "spider_base:token-owner-delete",
            kwargs={
                "token": self.home.token
            }
        )

    def test_filtered_token(self):
        token1 = self.home.authtokens.create(extra={"intentions": []})
        self.app.get(self.deleteurl)
        response = self.app.get(
            self.deleteurl
        )
        jtoken = response.json["tokens"][0]
        self.assertLess(len(jtoken["name"]), len(token1.token))
        self.assertFalse(jtoken["restricted"])
        self.assertFalse(jtoken["token"])
        self.assertFalse(jtoken["created"])

    def test_add(self):
        token1 = self.home.authtokens.create()
        self.app.get(self.deleteurl)
        response = self.app.post(
            self.deleteurl,
            params={
                "add_token": True
            },
            headers={
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )

        jsonob = response.json
        found_token1 = False
        new_tokenid = None
        for jtoken in jsonob["tokens"]:
            if jtoken["id"] == token1.id:
                found_token1 = True
                self.assertLess(len(jtoken["name"]), len(token1.token))
                self.assertFalse(jtoken["restricted"])
                self.assertFalse(jtoken["created"])
            else:
                new_tokenid = jtoken["id"]
                self.assertTrue(jtoken["token"])
                self.assertTrue(jtoken["created"])
                self.assertFalse(jtoken["restricted"])
        self.assertTrue(found_token1)
        self.assertTrue(self.home.authtokens.filter(id=new_tokenid))

    def test_add_restricted(self):
        token1 = self.home.authtokens.create()
        self.app.get(self.deleteurl)
        response = self.app.post(
            self.deleteurl,
            params={
                "add_token": True,
                "restrict": True
            },
            headers={
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )

        jsonob = response.json
        found_token1 = False
        new_tokenid = None
        for jtoken in jsonob["tokens"]:
            if jtoken["id"] == token1.id:
                found_token1 = True
                self.assertLess(len(jtoken["name"]), len(token1.token))
                self.assertFalse(jtoken["restricted"])
                self.assertFalse(jtoken["created"])
            else:
                new_tokenid = jtoken["id"]
                self.assertTrue(jtoken["token"])
                self.assertTrue(jtoken["created"])
                self.assertTrue(jtoken["restricted"])
        self.assertTrue(found_token1)
        self.assertTrue(self.home.authtokens.filter(id=new_tokenid))

    def test_delete_post(self):
        token1 = self.home.authtokens.create()
        token2 = self.home.authtokens.create()
        response = self.app.get(self.deleteurl)
        jsonob = response.json
        found_token1 = False
        found_token2 = False
        for jtoken in jsonob["tokens"]:
            if jtoken["id"] == token1.id:
                found_token1 = True
            elif jtoken["id"] == token2.id:
                found_token2 = True
        self.assertTrue(found_token1)
        self.assertTrue(found_token2)
        response = self.app.post(
            self.deleteurl,
            params={
                "delete_tokens": [token1.id]
            },
            headers={
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )
        jsonob = response.json
        self.assertFalse(self.home.authtokens.filter(id=token1.id))
        self.assertEqual(len(jsonob["tokens"]), 1)
        self.assertEqual(jsonob["tokens"][0]["id"], token2.id)

    def test_delete_json(self):
        token1 = self.home.authtokens.create()
        token2 = self.home.authtokens.create()
        response = self.app.get(self.deleteurl)
        jsonob = response.json
        found_token1 = False
        found_token2 = False
        for jtoken in jsonob["tokens"]:
            if jtoken["id"] == token1.id:
                found_token1 = True
            elif jtoken["id"] == token2.id:
                found_token2 = True
        self.assertTrue(found_token1)
        self.assertTrue(found_token2)
        response = self.app.post(
            self.deleteurl,
            params=json.dumps({
                "delete_tokens": [token1.id]
            }),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )
        jsonob = response.json
        self.assertFalse(self.home.authtokens.filter(id=token1.id))
        self.assertEqual(len(jsonob["tokens"]), 1)
        self.assertEqual(jsonob["tokens"][0]["id"], token2.id)
