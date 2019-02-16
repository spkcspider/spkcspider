
from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse


from rdflib import Graph, Literal, XSD

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
from spkcspider.apps.spider.helpers import merge_get_url
from spkcspider.apps.spider.signals import update_dynamic


class ProtectionTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    @override_settings(DEBUG=True)
    def test_login_only(self):
        # FIXME: lacks assigned Protections
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={"token": home.token}
        )
        # prefer = get tokens, but tokens should be stripped in redirect
        viewurl = "?".join((home.get_absolute_url(), "token=prefer"))
        response = self.app.get(updateurl, user="testuser1")
        form = response.forms["componentForm"]
        form["public"] = True
        form["required_passes"] = 10
        response = form.submit(user="testuser1")
        home.refresh_from_db()
        self.assertEqual(home.strength, 4)

        del form
        del response
        self.app.set_user(user=None)
        self.app.reset()
        response = self.app.get(viewurl).follow()

        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.assertTrue(response.location.startswith(viewurl))
        # self.assertNotIn("token=", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

        response = self.app.get(updateurl, user="testuser1")
        form = response.forms["componentForm"]
        form["public"] = False
        response = form.submit(user="testuser1")
        home.refresh_from_db()
        self.assertEqual(home.strength, 9)

        del form
        del response
        self.app.set_user(user=None)
        self.app.reset()
        response = self.app.get(viewurl).follow()
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.assertTrue(response.location.startswith(viewurl))
        # self.assertNotIn("token=", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

    def test_protections(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        home.protections
        # activate captcha

    def test_upgrade(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        public = self.user.usercomponent_set.filter(name="public").first()
        self.assertTrue(public)
        # activate upgrade method of LoginProtection
