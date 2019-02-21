
import unittest

from django_webtest import TransactionWebTest
from django.urls import reverse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.apps.spider.signals import update_dynamic

from spkcspider.apps.spider_keys.models import PublicKey
# Create your tests here.


class KeyTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send_robust(self)


    @unittest.expectedFailure
    def test_keys(self):
        home = self.user.usercomponent_set.get(name="home")
        privkey = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        pempriv = privkey.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        pempub = privkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        self.app.set_user(user="testuser1")
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "PublicKey"
            }
        )
        with self.subTest(msg="block invalid keys"):
            response = self.app.get(createurl)
            form = response.form
            form["key"] = pempriv
            form["note"] = "invalid"
            response = form.submit()
            self.assertFalse(PublicKey.objects.filter(note="invalid"))

        with self.subTest(msg="allow valid keys"):
            response = self.app.get(createurl)
            form = response.form
            form["key"] = pempub
            form["note"] = "valid"
            response = form.submit().follow()
            self.assertTrue(PublicKey.objects.filter(note="valid"))

    def test_anchor_server(self):
        home = self.user.usercomponent_set.get(name="home")
        self.app.set_user(user="testuser1")
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorServer"
            }
        )
        response = self.app.get(createurl)
        self.assertEqual(response.status_code, 200)
        # no args
        response = response.form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(home.contents.first())

    def test_anchor_signed_server(self):
        home = self.user.usercomponent_set.get(name="home")
        self.app.set_user(user="testuser1")
        privkey = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        pempriv = privkey.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        pempub = privkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
