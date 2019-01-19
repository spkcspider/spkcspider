# import unittest

from django.test import TransactionTestCase
from django_webtest import TransactionWebTest
from django.test import Client
from django.db.utils import IntegrityError
from django.urls import reverse

from rdflib import Graph

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.models import UserComponent, AssignedContent
from spkcspider.apps.spider.signals import update_dynamic
# Create your tests here.


class BasicComponentTest(TransactionTestCase):
    def setUp(self):
        self.client = Client(secure=True, enforce_csrf_checks=True)
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc", is_active=True
        )

    def test_welcome(self):
        self.user.usercomponent_set.get(name="public")
        self.user.usercomponent_set.get(name="home")

    def test_index(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        self.assertTrue(index)
        with self.assertRaises(IntegrityError):
            self.user.usercomponent_set.create(name="index")
        indexurl = reverse(
            "spider_base:ucontent-list",
            kwargs={
                "nonce": index.nonce,
                "id": index.id
            }
        )
        self.assertEqual(indexurl, index.get_absolute_url())
        response = self.client.get(indexurl)
        self.assertEqual(response.status_code, 302)
        target = "{}?next={}".format(reverse("auth:login"), indexurl)
        self.assertRedirects(response, target)
        self.client.login(username="testuser1", password="abc")
        response = self.client.get(indexurl)
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 0)

        # try to update
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "name": "index",
                "nonce": index.nonce
            }
        )
        response = self.client.get(updateurl)
        self.assertEqual(response.status_code, 200)

    def test_public(self):
        for i in range(1, 4):
            UserComponent.objects.create(
                user=self.user,
                public=True,
                required_passes=0,
                name="test%s" % i
            )
            self.assertTrue(self.user.usercomponent_set.get(name="test%s" % i))
        self.assertTrue(self.user.usercomponent_set.get(name="public"))

        response = self.client.get('/spider/ucs/')
        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 3)
        response = self.client.get('/spider/ucs/?page=2')
        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 1)

        # Issue a GET request.
        response = self.client.get('/spider/ucs/?raw=true')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "ascii"), format="turtle")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 3)

        # Issue a GET request.
        response = self.client.get('/spider/ucs/?raw=true&page=2')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "ascii"), format="turtle")
        self.assertEqual(
            sum(
                1 for _ in g.triples((None, spkcgraph["components"], None))
            ), 1
        )


class AdvancedComponentTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_contents(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        public = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(public)
        self.app.set_user("testuser1")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "home",
                "type": "AnchorServer"
            }
        )
        form = self.app.get(createurl).forms[0]
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(home.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "public",
                "type": "AnchorServer"
            }
        )
        form = self.app.get(createurl).forms[0]
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(public.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "public",
                "type": "TravelProtection"
            }
        )
        response = self.app.get(createurl, expect_errors=True, status=404)
        self.assertEqual(response.status_code, 404)

        return
        ################################

        createurlindex = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "index",
                "type": "Text"
            }
        )
        form = self.app.get(createurlindex).forms[0]
        form.action = createurlindex
        form['name'] = "public"
        response = form.submit().follow()
        # cross posting is possible but causes a redirect back to right path
        # here a correction
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AssignedContent.objects.count(), 1)
