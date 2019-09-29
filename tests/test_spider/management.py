from django.core.management import call_command
from django.test import TransactionTestCase
from io import StringIO

from spkcspider.apps.spider.models import (
    AuthToken, UserComponent, ReferrerObject
)
from spkcspider.apps.spider_accounts.models import SpiderUser


class ManagementTests(TransactionTestCase):
    def setUp(self):
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc", is_active=True
        )

    def test_update_dynamic_content(self):
        out = StringIO()
        call_command('update_dynamic_content', stdout=out)
        self.assertNotIn('failed', out.getvalue())

    def test_revoke_persistent_auth_tokens(self):
        uc = UserComponent.objects.get(
            name="home"
        )
        AuthToken.objects.create(
            persist=-1,
            usercomponent=uc
        )
        AuthToken.objects.create(
            persist=0,
            usercomponent=uc
        )
        AuthToken.objects.create(
            persist=1,
            usercomponent=uc
        )
        out = StringIO()
        call_command('revoke_auth_tokens', stdout=out)
        self.assertEqual(AuthToken.objects.count(), 2)
        self.assertEqual(out.getvalue(), "count: 1\n")

        out = StringIO()
        call_command('revoke_auth_tokens', "--anchor=all", stdout=out)
        self.assertEqual(AuthToken.objects.count(), 0)
        self.assertEqual(out.getvalue(), "count: 2\n")

    def test_revoke_anchor_component_auth_tokens(self):
        uc = UserComponent.objects.get(
            name="home"
        )
        AuthToken.objects.create(
            persist=-1,
            usercomponent=uc
        )
        AuthToken.objects.create(
            persist=0,
            usercomponent=uc
        )
        AuthToken.objects.create(
            persist=1,
            usercomponent=uc
        )

        out = StringIO()
        call_command('revoke_auth_tokens', '--anchor=1', stdout=out)
        self.assertEqual(AuthToken.objects.count(), 2)
        self.assertEqual(out.getvalue(), "count: 1\n")

        out = StringIO()
        call_command('revoke_auth_tokens', "--anchor=0", stdout=out)
        self.assertEqual(AuthToken.objects.count(), 1)
        self.assertEqual(out.getvalue(), "count: 1\n")

        out = StringIO()
        call_command('revoke_auth_tokens', "--anchor=persist", stdout=out)
        self.assertEqual(AuthToken.objects.count(), 1)
        self.assertEqual(out.getvalue(), "count: 0\n")

    def test_revoke_referrer_auth_tokens(self):
        uc = UserComponent.objects.get(
            name="home"
        )
        AuthToken.objects.create(
            persist=-1,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com"
            )[0]
        )
        AuthToken.objects.create(
            persist=0,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com"
            )[0]
        )
        AuthToken.objects.create(
            persist=1,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com"
            )[0]
        )
        AuthToken.objects.create(
            persist=1,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com/test"
            )[0]
        )
        AuthToken.objects.create(
            persist=-1,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com/test"
            )[0]
        )
        AuthToken.objects.create(
            persist=0,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example.com/test"
            )[0]
        )
        AuthToken.objects.create(
            persist=0,
            usercomponent=uc,
            referrer=ReferrerObject.objects.get_or_create(
                url="http://example2.com/test"
            )[0]
        )

        out = StringIO()
        call_command(
            'revoke_auth_tokens', '--referrer=http://example.com', stdout=out
        )
        self.assertEqual(AuthToken.objects.count(), 4)
        self.assertEqual(out.getvalue(), "count: 3\n")

        out = StringIO()
        call_command(
            'revoke_auth_tokens', '--referrer=http://example.com/test',
            '--anchor=persist', stdout=out
        )
        self.assertEqual(AuthToken.objects.count(), 2)
        self.assertEqual(out.getvalue(), "count: 2\n")

        out = StringIO()
        call_command(
            'revoke_auth_tokens', '--oldest=1',
            '--anchor=all', stdout=out
        )
        self.assertEqual(AuthToken.objects.count(), 1)
        self.assertEqual(out.getvalue(), "count: 1\n")
        # the last is the latest and not affected
        self.assertTrue(AuthToken.objects.get(
            referrer__url="http://example2.com/test",
        ))
