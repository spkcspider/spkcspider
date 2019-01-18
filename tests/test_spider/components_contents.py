import unittest

from django.test import TransactionTestCase
from django.test import Client
from django.db.utils import IntegrityError
from django.urls import reverse

from rdflib import Graph

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.models import UserComponent
from spkcspider.apps.spider.signals import update_dynamic
# Create your tests here.


class ComponentTest(TransactionTestCase):
    def setUp(self):
        self.client = Client(secure=True, enforce_csrf_checks=True)
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc", is_active=True
        )

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

    @unittest.expectedFailure
    def test_contents(self):
        update_dynamic.send_robust(self)
        public = self.user.usercomponent_set.get(name="public")
        home = self.user.usercomponent_set.get(name="home")

        self.client.login(username="testuser1", password="abc")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "home",
                "type": "AnchorServer"
            }
        )

        response = self.client.post(createurl)
        # Check that the response is redirect.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(home.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "public",
                "type": "AnchorServer"
            }
        )
        response = self.client.post(createurl)
        # Check that the response is redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(public.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "name": "public",
                "type": "TravelProtection"
            }
        )
        response = self.client.post(createurl)
        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 404)
