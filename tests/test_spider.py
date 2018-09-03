from django.test import TestCase
from django.test import Client

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.models import UserComponent
# Create your tests here.


class ComponentTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc"
        )
        UserComponent.objects.create(
            user=self.user, name="public", public=True
        )

    def test_index_creation(self):
        self.assertTrue(self.user.usercomponent_set.get(name="index"))
        with self.assertRaises(Exception):
            self.user.usercomponent_set.create(name="index")

    def test_glob_index(self):
        # Issue a GET request.
        response = self.client.get('/spider/ucs/')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
