# import unittest

from rdflib import Graph, Literal, XSD

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django_webtest import TransactionWebTest
from spkcspider.apps.spider.models import AssignedContent, UserComponent
from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.constants import spkcgraph
from spkcspider.utils.security import create_b64_id_token

# Create your tests here.


class BasicComponentTest(TransactionTestCase):
    def setUp(self):
        self.client = Client(secure=True, enforce_csrf_checks=True)
        self.user = SpiderUser.objects.create_user(
            username="testuser1", password="abc", is_active=True
        )

    def test_welcome(self):
        self.user.usercomponent_set.get(name="public")
        self.user.usercomponent_set.get(name="home")

    def test_token_generation(self):
        for i in range(0, 100):
            i2 = create_b64_id_token(i, "_")
            try:
                i2.encode("ascii")
            except UnicodeEncodeError:
                self.assertTrue(False)
            self.assertIsInstance(i2, str)
            self.assertNotIn("–", i2)
            self.assertNotIn("\\", i2)

    def test_index(self):
        SpiderUser.objects.create_user(
            username="testuser2", password="abc", is_active=True
        )
        index = self.user.usercomponent_set.filter(name="index").first()
        self.assertTrue(index)
        with self.assertRaises(IntegrityError):
            self.user.usercomponent_set.create(name="index")
        indexurl = reverse(
            "spider_base:ucontent-list",
            kwargs={
                "token": index.token,
            }
        )
        self.assertEqual(indexurl, index.get_absolute_url())
        response = self.client.get(indexurl)
        self.assertEqual(response.status_code, 403)
        self.client.login(username="testuser2", password="abc")
        response = self.client.get(indexurl, status=403)
        self.assertEqual(response.status_code, 403)
        self.client.login(username="testuser1", password="abc")
        response = self.client.get(indexurl)
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 0)

        # try to update
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "token": index.token
            }
        )
        response = self.client.get(updateurl)
        self.assertEqual(response.status_code, 200)

    def test_public(self):
        for i in range(1, 4):
            UserComponent.objects.create(
                user=self.user,
                public=True,
                required_passes=0,
                name="test%s" % i
            )
            self.assertTrue(self.user.usercomponent_set.get(name="test%s" % i))
        self.assertTrue(self.user.usercomponent_set.get(name="public"))

        response = self.client.get('/spider/components/')
        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 3)
        response = self.client.get('/spider/components/?page=2')
        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="html")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 1)

        # Issue a GET request.
        response = self.client.get('/spider/components/?raw=true')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="turtle")
        self.assertEqual(sum(
            1 for _ in g.triples((None, spkcgraph["components"], None))
        ), 3)

        # Issue a GET request.
        response = self.client.get('/spider/components/?raw=true&page=2')

        # Check that the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        g = Graph()
        g.parse(data=str(response.content, "utf8"), format="turtle")
        self.assertEqual(
            sum(
                1 for _ in g.triples((None, spkcgraph["components"], None))
            ), 1
        )


class AdvancedComponentTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send(self)

    def test_private(self):
        private = self.user.usercomponent_set.create(
            name="privat",
            required_passes=1
        )
        self.assertEqual(private.strength, 9)
        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": private.token,
                "type": "AnchorServer"
            }
        )
        listurl = reverse(
            "spider_base:ucontent-list",
            kwargs={
                "token": private.token
            }
        )
        self.app.set_user("testuser1")
        with self.subTest("test access own resources"):
            response = self.app.get(listurl)
            self.assertEqual(response.status_code, 200)
            response = self.app.get(createurl)
            self.assertEqual(response.status_code, 200)

        # check that other non admins have no access
        self.app.set_user("testuser2")
        with self.subTest("test access foreign resources"):
            response = self.app.get(listurl, status=403)
            self.assertEqual(response.status_code, 403)
            response = self.app.get(createurl, status=403)
            self.assertEqual(response.status_code, 403)

        SpiderUser.objects.filter(
            username="testuser2"
        ).update(is_staff=True)
        # still require permission
        with self.subTest("test access foreign resources as staff"):
            response = self.app.get(listurl, status=403)
            self.assertEqual(response.status_code, 403)
            response = self.app.get(createurl, status=403)
            self.assertEqual(response.status_code, 403)

        user2 = SpiderUser.objects.filter(
            username="testuser2"
        ).first()

        content_type = ContentType.objects.get_for_model(UserComponent)
        permission = Permission.objects.get(
            codename='view_usercomponent',
            content_type=content_type,
        )
        user2.user_permissions.add(permission)
        with self.subTest("test access foreign resources with permission"):
            self.assertTrue(user2.has_perm('spider_base.view_usercomponent'))
            # has permission now
            # response = self.app.get(listurl)
            # self.assertEqual(response.status_code, 200)
            response = self.app.get(createurl, status=403)
            self.assertEqual(response.status_code, 403)

        # check superuser
        SpiderUser.objects.filter(
            username="testuser1"
        ).update(is_superuser=True)

        private = user2.usercomponent_set.create(
            name="privat",
            required_passes=1
        )
        self.assertEqual(private.strength, 9)
        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": private.token,
                "type": "AnchorServer"
            }
        )
        listurl = reverse(
            "spider_base:ucontent-list",
            kwargs={
                "token": private.token
            }
        )
        self.app.set_user("testuser1")

        with self.subTest("test access foreign resources as superuser"):
            response = self.app.get(listurl)
            self.assertEqual(response.status_code, 200)
            response = self.app.get(createurl, status=403)
            self.assertEqual(response.status_code, 403)

    def test_token(self):
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        updateurl = reverse(
            "spider_base:ucomponent-update",
            kwargs={
                "token": home.token,
            }
        )
        self.app.set_user("testuser1")
        delete_form = self.app.get(updateurl).forms["deleteForm"]
        response = delete_form.submit()
        self.assertEqual(response.status_code, 200)

        self.app.set_user("testuser2")
        # disguised
        response = self.app.get(updateurl, status=404)
        self.assertEqual(response.status_code, 404)
        # unauthorized access to update
        response = delete_form.submit(status=403).maybe_follow()
        self.assertEqual(response.status_code, 403)

        # TODO: test token creation and deletion

    def test_domainauth(self):
        self.app.set_user("testuser1")
        index = self.user.usercomponent_set.filter(name="index").first()
        self.assertTrue(index)
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorServer"
            }
        )
        response = self.app.get(createurl)
        response.forms["main_form"].submit().follow()
        content = home.contents.first()
        for url, turtle in [
            (reverse(
                "spider_base:ucontent-access",
                kwargs={
                    "token": content.token,
                    "access": "update"
                }
            ), False),
            (createurl, False),
            (reverse(
                "spider_base:ucontent-list",
                kwargs={
                    "token": home.token,
                }
            ), True),
            (reverse(
                "spider_base:ucontent-access",
                kwargs={
                    "token": content.token,
                    "access": "view"
                }
            ), True)
        ]:
            with self.subTest(msg="url: \"%s\" html" % url):
                response = self.app.get(url)
                g = Graph()
                g.parse(data=str(response.content, "utf8"), format="html")
                self.assertEqual(sum(
                    1 for _ in g.triples((
                        None,
                        spkcgraph["feature:name"],
                        Literal("domainauth-url", datatype=XSD.string)
                    ))
                ), 1)
            if turtle:
                with self.subTest(msg="url: \"%s\" turtle" % url):
                    response = self.app.get(url+"?raw=true")
                    g = Graph()
                    g.parse(
                        data=str(response.content, "utf8"), format="turtle"
                    )
                    self.assertEqual(sum(
                        1 for _ in g.triples((
                            None,
                            spkcgraph["feature:name"],
                            Literal("domainauth-url", datatype=XSD.string)
                        ))
                    ), 1)

    def test_contents(self):
        index = self.user.usercomponent_set.filter(name="index").first()
        self.assertTrue(index)
        home = self.user.usercomponent_set.filter(name="home").first()
        self.assertTrue(home)
        public = self.user.usercomponent_set.filter(name="public").first()
        self.assertTrue(public)
        self.app.set_user("testuser1")

        # try to create
        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": home.token,
                "type": "AnchorServer"
            }
        )
        form = self.app.get(createurl).forms["main_form"]
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(home.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": public.token,
                "type": "AnchorServer"
            }
        )
        form = self.app.get(createurl).forms["main_form"]
        response = form.submit().follow()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(public.contents.count(), 1)

        createurl = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": public.token,
                "type": "UserTagLayout"
            }
        )
        response = self.app.get(createurl, status=404)
        self.assertEqual(response.status_code, 404)

        createurlindex = reverse(
            "spider_base:ucontent-add",
            kwargs={
                "token": index.token,
                "type": "Text"
            }
        )
        response = self.app.get(createurlindex)
        form = response.forms["main_form"]
        form.action = createurlindex
        form['content_control-usercomponent'] = public.id
        form['content_control-name'] = "newfieldname"
        form['text'] = "foobar"
        response = form.submit()
        location = response.location
        response = response.follow()
        # should redirect to public component
        self.assertEqual(response.status_code, 200)
        self.assertEqual(public.contents.count(), 2)
        url = public.contents.get(
            info__contains="\x1ename=newfieldname\x1e"
        ).get_absolute_url("update")
        self.assertEqual(location, url)
        form = response.forms["main_form"]
        self.assertEqual(form["text"].value, "foobar")
        form['content_control-new_static_token'] = "12"
        form['text'] = "foobart"
        form['content_control-name'] = "newfieldname2"
        response = form.submit().follow()
        self.assertEqual(response.forms["main_form"]["text"].value, "foobart")
        with self.assertRaises(AssignedContent.DoesNotExist):
            public.contents.get(
                info__contains="\x1ename=newfieldname\x1e"
            )

        with self.subTest(msg="match uc with from_url_part"):
            url = public.contents.get(
                info__contains="\x1ename=newfieldname2\x1e"
            ).get_absolute_url("fsooso")
            self.assertEqual(
                public, UserComponent.objects.from_url_part(url)
            )
            url = public.get_absolute_url()
            self.assertEqual(
                public, UserComponent.objects.from_url_part(url)
            )
            self.assertEqual(
                public, UserComponent.objects.from_url_part(
                    "{}/list".format(public.token)
                )
            )
            with self.assertRaises(public.DoesNotExist):
                UserComponent.objects.from_url_part("7_8383/list")
            with self.assertRaises(public.DoesNotExist):
                UserComponent.objects.from_url_part("7_8383")

        with self.subTest(msg="match content with from_url_part"):
            content = public.contents.get(
                info__contains="\x1ename=newfieldname2\x1e"
            )
            url = content.get_absolute_url("slksdkl")
            cs = AssignedContent.objects.from_url_part(
                url, info="name=newfieldname2"
            )
            self.assertEqual(content, cs[0])
            self.assertEqual(content, cs[1])
            self.assertEqual(
                content, AssignedContent.objects.from_url_part(
                    url, info=["name=newfieldname2"]
                )[0]
            )
            with self.assertRaises(content.DoesNotExist):
                AssignedContent.objects.from_url_part(
                    url, info=["name=notexistent"]
                )
            with self.assertRaises(content.DoesNotExist):
                # is no feature so it should fail
                AssignedContent.objects.from_url_part(
                    url, info=["name=newfieldname2"], check_feature=True
                )
            with self.assertRaises(content.DoesNotExist):
                AssignedContent.objects.from_url_part(
                    url, info=["name=newfieldname2"], variant="sklskls"
                )
            url = public.get_absolute_url()
            cs = AssignedContent.objects.from_url_part(
                url, info=["type=Text", "id={}".format(content.id)]
            )
            self.assertEqual(content, cs[0])
            self.assertEqual(None, cs[1])
            self.assertEqual(
                content, AssignedContent.objects.from_url_part(
                    "{}/list".format(public.token),
                    info=["name=newfieldname2"],
                    variant="Text"
                )[0]
            )
            with self.assertRaises(content.MultipleObjectsReturned):
                AssignedContent.objects.from_url_part("7_8383/view", info="")
            with self.assertRaises(content.MultipleObjectsReturned):
                AssignedContent.objects.from_url_part("7_8383/list", info=[])
            with self.assertRaises(content.DoesNotExist):
                AssignedContent.objects.from_url_part(
                    "7_8383/view", info=["name=newfieldname2"]
                )
            with self.assertRaises(content.DoesNotExist):
                AssignedContent.objects.from_url_part(
                    "7_8383/list", info=["name=newfieldname2"]
                )
            with self.assertRaises(content.DoesNotExist):
                AssignedContent.objects.from_url_part("7_8383", info=[])
