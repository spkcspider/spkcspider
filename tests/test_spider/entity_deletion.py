
import datetime

from django.test import override_settings
from django.urls import reverse
from django_webtest import TransactionWebTest
from rdflib import RDF, XSD, Graph, Literal, URIRef

from spkcspider.apps.spider.signals import update_dynamic
from spkcspider.apps.spider_accounts.models import SpiderUser
from spkcspider.constants.rdf import spkcgraph


class DeletionTest(TransactionWebTest):
    fixtures = ['test_default.json']

    def setUp(self):
        super().setUp()
        self.user = SpiderUser.objects.get(
            username="testuser1"
        )
        update_dynamic.send(self)

    def test_structure_rdfa(self):
        self.app.set_user(user="testuser1")
        index = self.user.usercomponent_set.get(name="index")
        self.user.usercomponent_set.create(name="empty")
        deleteurl = reverse(
            "spider_base:entity-delete",
            kwargs={
                "token": index.token
            }
        )
        response = self.app.get(deleteurl)
        g = Graph()
        g.parse(data=response.text, format="html")
        tmp = list(g.query(
            """
                SELECT ?component ?content
                WHERE {
                    ?base spkc:components ?component .
                    ?component spkc:contents ?content .
                }
            """,
            initNs={"spkc": spkcgraph}
        ))
        # every component was found
        self.assertGreaterEqual(len(tmp), self.user.usercomponent_set.count())
        query = self.user.usercomponent_set.filter(contents__isnull=True)
        # check test prequisites
        assert query.count() > 0

        for component in query:
            g.query(
                """
                    SELECT ?component ?content
                    WHERE {
                        ?base spkc:components ?component .
                        ?component spkc:contents ?content .
                    }
                """,
                initNs={"spkc": spkcgraph},
                initBindings={
                    "content": RDF.nil
                }
            )

    def test_structure_json(self):
        self.app.set_user(user="testuser1")
        index = self.user.usercomponent_set.get(name="index")
        deleteurl = reverse(
            "spider_base:entity-delete",
            kwargs={
                "token": index.token
            }
        )
        response = self.app.get(
            deleteurl,
            headers={
                "Accept": "application/json"
            }
        )
        self.assertEqual(
            len(response.json), self.user.usercomponent_set.count()
        )

    @override_settings(
        SPIDER_COMPONENTS_DELETION_PERIODS={}
    )
    def test_deletion_no_gracetime(self):
        self.app.set_user(user="testuser1")
        index = self.user.usercomponent_set.get(name="index")
        deleteurl = reverse(
            "spider_base:entity-delete",
            kwargs={
                "token": index.token
            }
        )
        self.user.usercomponent_set.create(name="comp1")
        self.user.usercomponent_set.create(name="comp2")
        response = self.app.get(deleteurl)
        g = Graph()
        g.parse(data=response.text, format="html")
        tmp = set(map(lambda x: x[0], g.query(
            """
                SELECT ?name
                WHERE {
                    ?base spkc:components ?component .
                    ?component spkc:deletion:active false .
                    ?component spkc:properties ?property_name.
                    ?property_name spkc:name ?prop_name_name ;
                                   spkc:value ?name .
                }
            """,
            initNs={"spkc": spkcgraph},
            initBindings={
                "prop_name_name": Literal("name", datatype=XSD.string)
            }
        )))
        self.assertIn(Literal("comp1", datatype=XSD.string), tmp)
        self.assertIn(Literal("comp2", datatype=XSD.string), tmp)
        response = self.app.post(
            deleteurl,
            {
                "delete_components": ["comp1", "comp2"]
            },
            headers={
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )
        g = Graph()
        g.parse(data=response.text, format="html")

        tmp = set(map(lambda x: x[0], g.query(
            """
                SELECT ?name
                WHERE {
                    ?base spkc:components ?component .
                    ?component spkc:deletion:active false .
                    ?component spkc:properties ?property_name.
                    ?property_name spkc:name ?prop_name_name ;
                                   spkc:value ?name .
                }
            """,
            initNs={"spkc": spkcgraph},
            initBindings={
                "base": URIRef(deleteurl),
                "prop_name_name": Literal("name", datatype=XSD.string)
            }
        )))
        self.assertNotIn(Literal("comp1", datatype=XSD.string), tmp)
        self.assertNotIn(Literal("comp2", datatype=XSD.string), tmp)

    @override_settings(
        SPIDER_COMPONENTS_DELETION_PERIODS={
            "comp1": datetime.timedelta(hours=5),
            "comp2": datetime.timedelta(hours=2)
        }
    )
    def test_deletion_gracetime(self):
        self.app.set_user(user="testuser1")
        index = self.user.usercomponent_set.get(name="index")
        deleteurl = reverse(
            "spider_base:entity-delete",
            kwargs={
                "token": index.token
            }
        )
        self.user.usercomponent_set.create(name="comp1")
        self.user.usercomponent_set.create(name="comp2")
        response = self.app.get(deleteurl)
        g = Graph()
        g.parse(data=response.text, format="html")
        tmp = set(map(lambda x: x[0], g.query(
            """
                SELECT ?name
                WHERE {
                    ?base spkc:components ?component .
                    ?component spkc:deletion:active false .
                    ?component spkc:properties ?property_name.
                    ?property_name spkc:name ?prop_name_name ;
                                   spkc:value ?name .
                }
            """,
            initNs={"spkc": spkcgraph},
            initBindings={
                "prop_name_name": Literal("name", datatype=XSD.string)
            }
        )))
        self.assertIn(Literal("comp1", datatype=XSD.string), tmp)
        self.assertIn(Literal("comp2", datatype=XSD.string), tmp)
        response = self.app.post(
            deleteurl,
            {
                "delete_components": ["comp1", "comp2"]
            },
            headers={
                "X-CSRFToken": self.app.cookies['csrftoken']
            }
        )
        g = Graph()
        g.parse(data=response.text, format="html")

        tmp = set(map(lambda x: x[0], g.query(
            """
                SELECT ?name
                WHERE {
                    ?base spkc:components ?component .
                    ?component spkc:deletion:active true .
                    ?component spkc:properties ?property_name.
                    ?property_name spkc:name ?prop_name_name ;
                                   spkc:value ?name .
                }
            """,
            initNs={"spkc": spkcgraph},
            initBindings={
                "prop_name_name": Literal("name", datatype=XSD.string)
            }
        )))
        self.assertIn(Literal("comp1", datatype=XSD.string), tmp)
        self.assertIn(Literal("comp2", datatype=XSD.string), tmp)
