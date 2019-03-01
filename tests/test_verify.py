
import re

from django.conf import settings
from django.test import override_settings
from django.contrib.staticfiles.testing import LiveServerTestCase
from django.urls import reverse

from rdflib import Graph, Literal, XSD

from django_webtest import WebTestMixin, DjangoTestApp

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.signals import update_dynamic

from tests.referrerserver import create_referrer_server

# Create your tests here.


class LiveDjangoTestApp(DjangoTestApp):
    def __init__(self, url, *args, **kwargs):
        super(DjangoTestApp, self).__init__(url, *args, **kwargs)


class VerifyTest(WebTestMixin, LiveServerTestCase):
    fixtures = ['test_default.json']
    app_class = LiveDjangoTestApp

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

    def renew_app(self):
        self.app = self.app_class(
            self.live_server_url,
            extra_environ=self.extra_environ
        )

    # @unittest.expectedFailure
    def test_verify(self):
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
        # login in live system first
        response = self.app.get(reverse(
            "auth:login"
        ))
        # required for csrf cookie
        self.app.set_cookie('csrftoken', self.app.cookies['csrftoken'])
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.app.set_cookie('sessionid', self.app.cookies['sessionid'])
        response = response.follow()
        response = self.app.get(createurl)
        self.assertEqual(response.status_code, 200)
        form = response.form
        form["layout"].value = "address"
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
        url = response.html.find(
            "a",
            attrs={"href": re.compile(".*view.*")}
        )
        self.assertTrue(url)
        url = url.attrs["href"]
        self.assertIn(home.contents.first().get_absolute_url(), url)
        # must be after retrieving link
        response = response.click(
            href=url, index=0
        )
        self.assertEqual(response.status_code, 200)
        fullurl = "{}{}".format(self.live_server_url, url)
        verifyurl = reverse("spider_verifier:create")
        response = None
        with override_settings(DEBUG=True):
            response = self.app.get(verifyurl)
            form = response.form
            form["url"] = fullurl
            response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=response.text, format="html")
        self.assertIn(
            (
                None, spkcgraph["hash.algorithm"], Literal(
                    getattr(
                        settings, "VERIFICATION_HASH_ALGORITHM",
                        settings.SPIDER_HASH_ALGORITHM
                    ).name,
                    datatype=XSD.string
                )
            ),
            g
        )
        self.assertIn(
            (None, spkcgraph["verified"], Literal(False)),
            g
        )
