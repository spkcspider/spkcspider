from django.urls import reverse
from django.test import override_settings

from django_webtest import TransactionWebTest
from webtest import Upload

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.signals import update_dynamic
# Create your tests here.


class TextFiletTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_guest_and_normal(self):
        home = self.user.usercomponent_set.get(name="home")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "Text"
            }
        )
        self.app.set_user(user="testuser1")
        form = self.app.get(createurl).form
        form.set("name", "foo")
        form.set("text", "foooo")
        for field in form.fields["editable_from"]:
            if field._value == str(home.id):
                field.checked = True
                break
        response = form.submit()
        updateurl = response.location
        response = response.follow()
        self.assertEqual(response.status_code, 200)
        # check that parameters are saved (don't reuse form from request)
        self.assertEqual(self.app.get(updateurl).form["text"].value, "foooo")
        # logout and clean session
        self.app.set_user(user=None)
        self.app.reset()

        textob = home.contents.first()
        self.assertEqual(updateurl, textob.get_absolute_url("update"))

        updateg_url = reverse(
            "spider_base:ucontent-access",
            kwargs={
                "token": textob.token,
                "access": "update_guest"
            }
        )

        # user update successfull
        response = self.app.get(reverse(
            "spider_base:ucontent-access",
            kwargs={
                "token": textob.token,
                "access": "view"
            }
        ))
        self.assertEqual(response.status_code, 200)
        response = response.click(href=updateg_url)
        form = response.form
        form.set("text", "nope")
        response = form.submit()

        self.assertEqual(self.app.get(updateg_url).form["text"].value, "nope")


class FileFiletTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)

    def test_upload_file(self):
        home = self.user.usercomponent_set.get(name="home")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "File"
            }
        )
        self.app.set_user(user="testuser1")
        form = self.app.get(createurl).form
        form["file"] = Upload("fooo", b"[]", "application/json")
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        durl = home.contents.first().get_absolute_url("download")
        with self.subTest(msg="Download django"):
            response = self.app.get(durl)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.body, b"[]")
        with self.subTest(msg="Download direct"):
            with override_settings(FILE_DIRECT_DOWNLOAD=True):
                response = self.app.get(durl)
                self.assertEqual(response.status_code, 302)
                # no server so skip, as it doesn't work
