

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse
from rdflib import Graph, XSD, Literal

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

        response2 = response.goto("{}?raw=true".format(
            home.contents.first().get_absolute_url("view")
        ))
        g = Graph()
        g.parse(data=response2.body, format="turtle")
        self.assertIn(
            (None, None, Literal("tag/country_code", datatype=XSD.string)),
            g
        )

    @override_settings(DEBUG=True)
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
            ctype__contains=VariantType.feature.value
        ).values_list("name", "id"))
        for i in range(0, len(features)):
            field = form.get("features", index=i)
            if field._value == str(features["PushedTag"]):
                field.checked = True
        response = form.submit()
        self.assertEqual(response.status_code, 200)
        # TODO: test pushed tags
