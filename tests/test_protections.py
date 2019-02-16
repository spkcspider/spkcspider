from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse


from rdflib import Graph, Literal, URIRef, XSD


from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.constants.static import spkcgraph
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
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={"token": home.token}
        )
        # prefer = get tokens, but tokens should be stripped in redirect
        viewurl = "?".join((home.get_absolute_url(), "token=prefer"))
        self.app.set_user(user="testuser1")
        response = self.app.get(updateurl)
        form = response.forms["componentForm"]
        form["public"] = True
        form["required_passes"] = 10
        response = form.submit()
        home.refresh_from_db()
        self.assertEqual(home.strength, 4)

        self.app.set_user(user=None)
        # resets session
        self.app.reset()
        response = self.app.get(viewurl).follow()
        g = Graph()
        g.parse(data=response.body, format="html")
        self.assertIn(
            (
                None,
                spkcgraph["strength"],
                Literal(10, datatype=XSD.integer)
            ),
            g
        )

        self.assertIn(
            (
                None,
                spkcgraph["name"],
                Literal("login", datatype=XSD.string)
            ),
            g
        )

        self.assertIn(
            (
                None,
                spkcgraph["name"],
                Literal("password", datatype=XSD.string)
            ),
            g
        )

        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.assertTrue(response.location.startswith(viewurl))
        # self.assertNotIn("token=", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

        self.app.set_user(user="testuser1")
        response = self.app.get(updateurl)
        form = response.forms["componentForm"]
        form["public"] = False
        response = form.submit()
        home.refresh_from_db()
        self.assertEqual(home.strength, 9)

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        response = self.app.get(viewurl).follow()
        g = Graph()
        g.parse(data=response.body, format="html")
        self.assertIn(
            (
                None,
                spkcgraph["strength"],
                Literal(10, datatype=XSD.integer)
            ),
            g
        )
        self.assertIn(
            (
                None,
                spkcgraph["name"],
                Literal("login", datatype=XSD.string)
            ),
            g
        )

        self.assertIn(
            (
                None,
                spkcgraph["name"],
                Literal("password", datatype=XSD.string)
            ),
            g
        )
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.assertTrue(response.location.startswith(viewurl))
        # self.assertNotIn("token=", response.location)
        response = response.follow()
        self.assertNotIn("SPKCProtectionForm", response.forms)

    @override_settings(DEBUG=True)
    def test_protections(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={"token": home.token}
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(updateurl)
        form = response.forms["componentForm"]
        form["protections_password-active"] = True
        form["protections_password-passwords"] = \
            "fooobar\nnubadkkkkkkkkkkkkkkkkkkkkkkkkkkdkskdksdkdkdkdkr"
        form["protections_password-allow_auth"] = True
        response = form.submit()
        home.refresh_from_db()
        self.assertGreater(home.strength, 5)

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        viewurl = "?".join((home.get_absolute_url(), "token=prefer"))
        response = self.app.get(viewurl)
        response.showbrowser()
        g = Graph()
        g.parse(data=response.body, format="html")
        baseurl = "{}{}".format(
            "http://testserver", home.get_absolute_url()
        )
        self.assertIn(
            (
                URIRef(baseurl),
                spkcgraph["strength"],
                None
            ),
            g
        )

        self.assertIn(
            (
                None,
                spkcgraph["name"],
                Literal("password", datatype=XSD.string)
            ),
            g
        )
