

from django_webtest import TransactionWebTest

import cryptography

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.signals import update_dynamic
# Create your tests here.


class KeyTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_keys(self):
        home = self.user.usercomponent_set.get(name="home")
        privkey, pubkey = None, None
        with self.subTest(msg="block invalid keys"):
            pass
            # TODO: test blocking of private keys, key validation

        with self.subTest(msg="allow valid keys"):
            pass
            # TODO: test valid keys

    def test_anchor_server(self):
        home = self.user.usercomponent_set.get(name="home")

    def test_anchor_signed_server(self):
        home = self.user.usercomponent_set.get(name="home")
        privkey, pubkey = None, None
