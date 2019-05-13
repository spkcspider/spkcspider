import os
from base64 import b64encode
from datetime import datetime as dt, timedelta as td

from django.test import override_settings
from django_webtest import TransactionWebTest
from django.urls import reverse


from rdflib import Graph, Literal, URIRef, XSD


from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.models import UserComponent
from spkcspider.apps.spider.constants import spkcgraph, TravelLoginType
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider.helpers import aesgcm_pbkdf2_cryptor
from spkcspider.apps.spider.protections import _pbkdf2_params


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
    def test_pw_protection(self):
        weak_pw = "fooobar"
        # not really but for the test
        strong_pw = "nubadkkkkkkkkkkkkkkkkkkkkkkkkkkdkskdksdkdkdkdkr"
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={"token": home.token}
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(updateurl)
        form = response.forms["componentForm"]
        form["required_passes"] = 1
        form["protections_password-active"] = True
        salt = form["protections_password-salt"].value.encode("ascii")
        c = aesgcm_pbkdf2_cryptor(
            form["protections_password-default_master_pw"].value,
            salt=salt, params=_pbkdf2_params
        )
        nonce = os.urandom(16)
        w = c.encrypt(nonce, weak_pw.encode("ascii"), None)
        form.fields["protections_password-passwords"][0].force_value(
            ":".join(map(lambda x: b64encode(x).decode("ascii"), [
                nonce, w
            ]))
        )

        nonce = os.urandom(16)
        w = c.encrypt(nonce, strong_pw.encode("ascii"), None)
        form.fields["protections_password-auth_passwords"][0].force_value(
            ":".join(map(lambda x: b64encode(x).decode("ascii"), [
                nonce, w
            ]))
        )
        response = form.submit()
        home.refresh_from_db()
        self.assertGreater(home.strength, 5)
        self.assertTrue(home.can_auth)

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        viewurl = "?".join((home.get_absolute_url(), "token=prefer"))
        response = self.app.get(viewurl)
        g = Graph()
        g.parse(data=response.body, format="html")
        baseurl = home.get_absolute_url()
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

        form = response.form
        form.set("password", weak_pw, index=0)
        response = form.submit()
        self.assertTrue(response.location.startswith(home.get_absolute_url()))

        authurl = "?".join(
            (home.get_absolute_url(), "intention=auth")
        )
        response = self.app.get(authurl)
        form = response.form
        form.set("password", strong_pw, index=0)
        response = form.submit()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorServer"
            }
        )
        response = self.app.get(createurl).form.submit()
        # home.refresh_from_db()
        self.assertGreater(home.contents.count(), 0)


class TravelProtectionTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_simple_login_without_travelprotection(self):
        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()
        response = self.app.get(reverse("spider_base:ucomponent-list"))
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("public", datatype=XSD.string)
            ),
            g
        )
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("home", datatype=XSD.string)
            ),
            g
        )

    def test_hide(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        response = form.submit()
        listurl = reverse("spider_base:ucomponent-list")
        response = self.app.get(listurl)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("public", datatype=XSD.string)
            ),
            g
        )
        self.assertNotIn(
            (
                None,
                spkcgraph["value"],
                Literal("home", datatype=XSD.string)
            ),
            g
        )

    def test_trigger_hide(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("login_protection", TravelLoginType.trigger_hide.value)
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        form["trigger_pws"].force_value(("abc",))
        response = form.submit()

        # must be resetted to set hashed passwords

        self.app.set_user(user=None)
        # resets session
        self.app.reset()
        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()
        # now even without trigger contents should be hidden
        # so reset session
        self.app.set_user(user=None)
        self.app.reset()

        # and fake login
        self.app.set_user(user="testuser1")

        listurl = reverse("spider_base:ucomponent-list")
        response = self.app.get(listurl)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("public", datatype=XSD.string)
            ),
            g
        )
        self.assertNotIn(
            (
                None,
                spkcgraph["value"],
                Literal("home", datatype=XSD.string)
            ),
            g
        )

    def test_hide_with_trigger(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        form["trigger_pws"].force_value(("abc",))
        response = form.submit()

        # must be resetted to set hashed passwords

        self.app.set_user(user=None)
        # resets session
        self.app.reset()
        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()

        listurl = reverse("spider_base:ucomponent-list")
        response = self.app.get(listurl)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("public", datatype=XSD.string)
            ),
            g
        )
        self.assertNotIn(
            (
                None,
                spkcgraph["value"],
                Literal("home", datatype=XSD.string)
            ),
            g
        )

    def test_hide_with_failing_trigger(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        form["trigger_pws"].force_value(("nope",))
        response = form.submit()

        # must be resetted to set hashed passwords

        self.app.set_user(user=None)
        # resets session
        self.app.reset()
        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()

        listurl = reverse("spider_base:ucomponent-list")
        response = self.app.get(listurl)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("public", datatype=XSD.string)
            ),
            g
        )
        self.assertIn(
            (
                None,
                spkcgraph["value"],
                Literal("home", datatype=XSD.string)
            ),
            g
        )

    def test_wipe(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        index_count = index.contents.count()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("login_protection", TravelLoginType.wipe.value)
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        response = form.submit()

        self.assertEqual(
            index.contents.count(), index_count+1
        )

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        # needs approval
        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()
        self.assertTrue(
            UserComponent.objects.filter(user=self.user, name="home").exists()
        )
        self.assertTrue(
            self.user.usercomponent_set.filter(name="home").exists()
        )
        g = index.contents.get(ctype__name="TravelProtection")
        g.content.approved = True
        g.content.clean()
        g.content.save()

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()
        self.assertFalse(
            UserComponent.objects.filter(user=self.user, name="home").exists()
        )
        self.assertFalse(
            self.user.usercomponent_set.filter(name="home").exists()
        )
        self.assertEqual(
            index.contents.count(), index_count
        )

    def test_wipe_user(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        index_count = index.contents.count()
        home = self.user.usercomponent_set.filter(name="home").first()
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "TravelProtection"
            }
        )
        self.app.set_user(user="testuser1")
        response = self.app.get(createurl)
        form = response.form
        form.set("start", dt.utcnow()-td(days=1))
        form.set("login_protection", TravelLoginType.wipe_user.value)
        form.set("protect_components", (home.id,))
        form.set("master_pw", "abc")
        response = form.submit()

        self.assertEqual(
            index.contents.count(), index_count+1
        )

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        response = self.app.get(reverse("auth:login"))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit().follow()

        # approve
        g = index.contents.get(ctype__name="TravelProtection")
        g.content.approved = True
        g.content.clean()
        g.content.save()

        self.app.set_user(user=None)
        # resets session
        self.app.reset()

        response = self.app.get(reverse(
            "auth:login"
        ))
        form = response.form
        form.set("username", "testuser1")
        form.set("password", "abc", index=0)
        response = form.submit()
        self.assertFalse(
            SpiderUser.objects.filter(
                username="testuser1"
            ).first()
        )
