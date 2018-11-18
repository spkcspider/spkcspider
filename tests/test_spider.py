from django.test import TestCase
from django.test import Client
from rdflib import Graph

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
# Create your tests here.


class ComponentTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc"
        )

    def test_index_creation(self):
        self.assertTrue(self.user.usercomponent_set.get(name="index"))
        with self.assertRaises(Exception):
            self.user.usercomponent_set.create(name="index")

    def test_glob_index(self):
        self.user.usercomponent_set.create(name="test1", public=True)
        self.user.usercomponent_set.create(name="test2", public=True)
        self.user.usercomponent_set.create(name="test3", public=True)
        # Issue a GET request.
        response = self.client.get('/spider/ucs/?raw=true')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(response, format="turtle")
        self.assertLength(list(
            g.triples((None, spkcgraph["components"], None))
        ), 4)
