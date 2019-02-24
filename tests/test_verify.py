
import unittest

from django.contrib.staticfiles.testing import LiveServerTestCase
from django.urls import reverse


from django_webtest import WebTestMixin, DjangoTestApp


from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider_tags.models import TagLayout
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

    @unittest.expectedFailure
    def test_verify(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "SpiderTag"
            }
        )
        # login in live system first
        response = self.app.get(createurl).follow()
        form = response.forms[0]
        form.set("password", "abc", index=0)
        response = form.submit()
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
        response = response.click(
            href=home.contents.first().get_absolute_url("view"), index=0
        )
        location = response.location
        breakpoint()
        self.assertEqual(response.status_code, 200)
