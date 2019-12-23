from django.test import override_settings
from django.urls import reverse
from django_webtest import TransactionWebTest
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider_accounts.models import SpiderUser
from webtest import Upload

# Create your tests here.


class TextFiletTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send(self)

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
        response = self.app.get(createurl)
        form = response.forms["main_form"]
        form.set("content_control-name", "foo")
        form.set("text", "foooo")
        form["editable_from"].select_multiple([str(home.id)])
        # force non-existing license name (should be created)
        form["license_name"].force_value("testval")
        response = form.submit()
        updateurl = response.location
        response = response.follow()
        self.assertEqual(response.status_code, 200)
        # check that parameters are saved (don't reuse form from request)
        form = self.app.get(updateurl).forms["main_form"]
        self.assertEqual(form["text"].value, "foooo")
        self.assertEqual(form["license_name"].value, "testval")
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
        # third form is special update form
        form = response.forms[2]
        form.set("text", "nope")
        response = form.submit()

        self.assertEqual(
            self.app.get(updateg_url).forms[2]["text"].value,
            "nope"
        )


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
        form = self.app.get(createurl).forms["main_form"]
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
                # no server so skip, as redirect won't work
