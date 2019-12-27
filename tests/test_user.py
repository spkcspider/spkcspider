
import logging

from django_webtest import TransactionWebTest

from spkcspider.apps.spider.models import UserInfo
from spkcspider.apps.spider.signals import logger as signal_logger
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider_accounts.models import SpiderUser


class UserInfoCreationTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )

    def test_userinfo_old(self):
        self.assertTrue(UserInfo.objects.filter(user=self.user))

    def test_userinfo_update_dynamic(self):
        UserInfo.objects.filter(user=self.user).delete()
        self.assertFalse(UserInfo.objects.filter(user=self.user))
        with self.assertLogs(signal_logger, logging.WARNING):
            update_dynamic.send(self)
        self.assertTrue(UserInfo.objects.filter(user=self.user))

    def test_userinfo_new(self):
        newuser = SpiderUser.objects.create_user(
            "newuser", email=None, password="abc"
        )
        self.assertTrue(UserInfo.objects.filter(user=newuser))
