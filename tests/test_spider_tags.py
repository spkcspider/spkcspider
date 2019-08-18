import re

from urllib.parse import parse_qs, urlsplit

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse
from rdflib import Graph, XSD, Literal, URIRef

import requests

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider_tags.models import (
    TagLayout, SpiderTag
)
from spkcspider.constants import VariantType, spkcgraph
from spkcspider.apps.spider.models import ContentVariant, AuthToken
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server

# Create your tests here.


class TagTest(TransactionWebTest):
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

    def test_user_tags(self):
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
        form = response.forms["main_form"]
        form["layout"].value = "address"
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        form = response.forms["main_form"]
        form["tag/name"] = "Alouis Alchemie AG"
        form["tag/place"] = "Holdenstreet"
        form["tag/street_number"] = "40C"
        form["tag/city"] = "Liquid-City"
        form["tag/post_code"] = "123456"
        form["tag/country_code"] = "de"
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        # test updates
        form = response.forms["main_form"]
        form["tag/country_code"] = "dedsdlsdlsd"
        response = form.submit()
        form = response.forms["main_form"]
        self.assertEqual(form["tag/country_code"].value, "dedsdlsdlsd")
        response = response.click(
            href=home.contents.first().get_absolute_url("view"), index=0
        )
        self.assertEqual(response.status_code, 200)

        response = response.click(
            href=home.contents.first().get_absolute_url("update")
        )
        form = response.forms["main_form"]
        self.assertEqual(form["tag/country_code"].value, "de")

        response2 = response.goto("{}?raw=true".format(
            home.contents.first().get_absolute_url("view")
        ))
        g = Graph()
        g.parse(data=response2.body, format="turtle")
        self.assertIn(
            (None, None, Literal("tag/country_code", datatype=XSD.string)),
            g
        )

    def test_user_tag_layout(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        self.assertTrue(index)
        self.app.set_user(user="testuser1")
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TagLayout"
            }
        )
        response = self.app.get(createurl)
        form = response.forms["main_form"]
        form["name"] = "foo"
        form["layout"] = """[
            {
                "key": "name",
                "field": "CharField",
                "nonhashable": false,
                "max_length": 12
            },
            {
                "key": "ab",
                "label": "name2",
                "field": "CharField",
                "nonhashable": false,
                "max_length": 12
            }
        ]"""
        response = form.submit().follow()
        url = response.html.find(
            "a",
            attrs={"href": re.compile(".*view.*")}
        )
        self.assertTrue(url)
        url = url.attrs["href"]
        response = self.app.get(url)
        form = response.forms[2]
        self.assertIn("tag/name", form.fields)
        self.assertIn("tag/ab", form.fields)

    def test_referenced_by(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        self.app.set_user(user="testuser1")
        TagLayout.objects.create(
            name="selfref",
            layout=[
                {
                    "key": "name",
                    "field": "CharField",
                    "max_length": 12
                },
                {
                    "key": "ref",
                    "field": "UserContentRefField",
                    "modelname": "spider_tags.SpiderTag",
                    "required": False
                }
            ]
        )
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "SpiderTag"
            }
        )

        response = self.app.get(createurl)
        form = response.forms["main_form"]
        form["layout"].value = "selfref"
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        form = response.forms["main_form"]
        form["tag/name"] = "f1"
        form.submit()
        stag = SpiderTag.objects.latest("associated_rel__created")

        response = self.app.get(createurl)
        form = response.forms["main_form"]
        form["layout"].value = "selfref"
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        form = response.forms["main_form"]
        form["tag/name"] = "f2"
        form["tag/ref"] = stag.id
        form.submit()

        stag2 = SpiderTag.objects.latest("associated_rel__created")
        self.assertNotEqual(stag.id, stag2.id)

        response = self.app.get(createurl)
        form = response.forms["main_form"]
        form["layout"].value = "selfref"
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        form = response.forms["main_form"]
        form["tag/name"] = "f3"
        form["tag/ref"] = stag2.id
        form.submit()
        stag3 = SpiderTag.objects.latest("associated_rel__created")
        self.assertNotEqual(stag3.id, stag2.id)

        viewurl = "{}?raw=embed".format(
            stag3.get_absolute_url()
        )
        response = self.app.get(viewurl)
        g = Graph()
        g.parse(data=response.text, format="turtle")
        self.assertIn(
            (
                None,
                None,
                Literal("f3", datatype=XSD.string)
            ), g
        )
        self.assertIn(
            (
                None,
                None,
                Literal("f2", datatype=XSD.string)
            ), g
        )
        self.assertIn(
            (
                None,
                None,
                Literal("f1", datatype=XSD.string)
            ), g
        )

    @override_settings(DEBUG=True, RATELIMIT_ENABLE=False)
    def test_pushed_tags(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={"token": home.token}
        )
        self.app.set_user(user="testuser1")
        form = self.app.get(updateurl).forms["componentForm"]
        features = dict(ContentVariant.objects.filter(
            ctype__contains=VariantType.component_feature.value
        ).values_list("name", "id"))
        # select checkbox
        for field in form.fields["features"]:
            if field._value == str(features["PushedTag"]):
                field.checked = True
                break
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        urls = home.features.get(name="PushedTag").feature_urls
        self.assertEqual(len(urls), 1)
        pushed_url = next(iter(urls)).url
        response = response.click(
            href=home.get_absolute_url(), index=0
        )
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=response.body, format="html")
        # required for referrer stuff
        self.assertIn(
            (
                URIRef("http://testserver{}".format(pushed_url)),
                spkcgraph["feature:name"],
                Literal("pushtag", datatype=XSD.string)
            ),
            g
        )

        # logout and clean session
        self.app.set_user(user=None)
        self.app.reset()

        response = response.goto("{}?raw=true".format(
            home.get_absolute_url()
        ))

        g2 = Graph()
        g2.parse(data=response.body, format="turtle")
        self.assertIn(
            (
                URIRef("http://testserver{}".format(pushed_url)),
                spkcgraph["feature:name"],
                Literal("pushtag", datatype=XSD.string)
            ),
            g2
        )

        response = self.app.get(
            "{}?intention=domain&referrer=http://{}:{}".format(
                home.get_absolute_url(),
                *self.refserver.socket.getsockname()
            )
        )
        query = parse_qs(urlsplit(response.location).query)
        self.assertTrue(
            response.location.startswith(
                "http://{}:{}".format(*self.refserver.socket.getsockname())
            )
        )

        response = requests.get(
            response.location, headers={"Connection": "close"}
        )
        response.raise_for_status()
        self.assertIn(query["hash"][0], response.text)
        token = self.refserver.tokens[query["hash"][0]]["token"]
        tokenob = AuthToken.objects.filter(token=token).first()
        self.assertTrue(tokenob)
        self.assertTrue(tokenob.referrer)

        response = self.app.get("{}?token={}".format(pushed_url, token))
        self.assertIn("address", response.json["layout"])
        response = self.app.post(
            "{}?token={}".format(pushed_url, token),
            {
                "layout": "address"
            }
        )
        response = response.follow()
        self.assertEqual(response.status_code, 200)
        form = response.forms[2]
        form["tag/name"] = "Alouis Alchemie AG"
        form["tag/place"] = "Holdenstreet"
        form["tag/street_number"] = "40C"
        form["tag/city"] = "Liquid-City"
        form["tag/post_code"] = "123456"
        form["tag/country_code"] = "de"
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.forms[2]["tag/city"].value,
            "Liquid-City"
        )
        response = self.app.get(
            "{}?raw=true".format(
                home.contents.first().get_absolute_url("view")
            )
        )

        g = Graph()
        g.parse(data=response.body, format="turtle")
        self.assertIn(
            (None, None, Literal("tag/country_code", datatype=XSD.string)),
            g
        )
        self.assertIn(
            (None, None, Literal("Alouis Alchemie AG", datatype=XSD.string)),
            g
        )
