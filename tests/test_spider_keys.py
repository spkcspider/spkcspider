import binascii

# import unittest
from django.urls import reverse
from django.conf import settings

from django_webtest import TransactionWebTest

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

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

    # @unittest.expectedFailure
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
            form["content_control-description"] = "invalid"
            response = form.submit()
            self.assertFalse(PublicKey.objects.filter(
                associated_rel__description="invalid"
            ))

        with self.subTest(msg="allow valid keys"):
            response = self.app.get(createurl)
            form = response.form
            form["key"] = pempub
            form["content_control-description"] = "valid"
            response = form.submit().follow()
            self.assertTrue(PublicKey.objects.filter(
                associated_rel__description="valid"
            ))

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
        pempub = privkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "PublicKey"
            }
        )
        response = self.app.get(createurl)
        form = response.form
        form["key"] = pempub
        form["content_control-description"] = "valid"
        response = form.submit().follow()
        keyob = PublicKey.objects.filter(
            associated_rel__description="valid"
        ).first()
        self.assertTrue(keyob)
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorKey"
            }
        )
        response = self.app.get(createurl)
        form = response.form
        form.select("key", value=str(keyob.id))
        response = form.submit()
        updateurl = response.location
        response = response.follow()
        form = response.form
        identifier = form["identifier"].value.encode("utf-8")

        chosen_hash = settings.SPIDER_HASH_ALGORITHM
        signature = privkey.sign(
            identifier,
            padding.PSS(
                mgf=padding.MGF1(chosen_hash),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            chosen_hash
        )

        with self.subTest(msg="block invalid signature"):
            response = self.app.get(updateurl)
            form = response.form
            form["signature"].value = signature
            response = form.submit()
            response = self.app.get(updateurl)
            form = response.form
            self.assertEqual(form["signature"].value, "<replaceme>")

        with self.subTest(msg="valid signature"):
            u = binascii.hexlify(signature).decode("ascii")
            response = self.app.get(updateurl)
            form = response.form
            form["signature"].value = u
            response = form.submit()
            response = self.app.get(updateurl)
            form = response.form
            self.assertEqual(response.status_code, 200)
            self.assertEqual(form["signature"].value, u)
