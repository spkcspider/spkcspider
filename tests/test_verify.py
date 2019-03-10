
# import unittest
import re
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.test import override_settings
from django.contrib.staticfiles.testing import LiveServerTestCase
from django.urls import reverse

from rdflib import Graph, Literal, XSD
from celery import uuid

from django_webtest import WebTestMixin, DjangoTestApp

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.verifier.validate import validate
from spkcspider.apps.verifier.models import DataVerificationTag
from spkcspider.apps.spider_tags.models import SpiderTag

from tests.referrerserver import create_referrer_server

# Create your tests here.


class LiveDjangoTestApp(DjangoTestApp):
    def __init__(self, url, *args, **kwargs):
        super(DjangoTestApp, self).__init__(url, *args, **kwargs)


class MockAsyncValidate(object):
    value_captured = frozenset()
    task_id = None
    tasks = {}

    @classmethod
    def AsyncResult(cls, task_id, *args, **kwargs):
        return cls.tasks[task_id]

    def successful(self):
        return True

    @classmethod
    def apply_async(cls, *args, **kwargs):
        self = cls()
        self.value_captured = kwargs["args"]
        self.task_id = uuid()
        cls.tasks[self.task_id] = self
        return self

    def get(self, *args, **kwargs):
        ret = validate(*self.value_captured)
        return ret.get_absolute_url()


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
    @patch(
        "spkcspider.apps.verifier.views.async_validate",
        new=MockAsyncValidate
    )
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
            verification_location = response.location
            response = response.follow()
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

        # add permissions

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        self.app.set_user("testuser1")

        tag = DataVerificationTag.objects.first()
        self.assertFalse(tag.checked)

        content_type = ContentType.objects.get_for_model(DataVerificationTag)
        permission = Permission.objects.get(
            codename='can_verify',
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # create url to admin of verifiedtag
        adminurl = reverse(
            "admin:spider_verifier_dataverificationtag_change",
            kwargs={"object_id": tag.id}
        )

        # now verify tag
        response = self.app.get(adminurl)
        self.assertEqual(response.status_code, 200)
        form = response.form
        form["verification_state"].select("verified")
        response = form.submit(name="_continue").maybe_follow()
        # and check if tag is verified now
        form = response.form
        self.assertEqual(form["verification_state"].value, "verified")
        tag.refresh_from_db()
        # check if checked is set (date of verification)
        self.assertTrue(tag.checked)
        response = self.app.get(verification_location)
        g = Graph()
        g.parse(data=response.text, format="html")
        # now check if checked date is in rdf annotated html page
        self.assertIn(
            (None, spkcgraph["verified"], Literal(tag.checked)),
            g
        )

        # check if verifier is entered in verified_urls
        response = self.app.get(SpiderTag.objects.first().get_absolute_url())
        g = Graph()
        g.parse(data=response.text, format="html")
        # now check if checked date is in rdf annotated html page
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal(verification_location, datatype=XSD.anyURI)
            ),
            g
        )
