

from django_webtest import TransactionWebTest

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

    # TODO: test keys and anchor
