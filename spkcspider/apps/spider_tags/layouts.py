__all__ = ("default_layouts", "initialize_layouts")

from django.utils.translation import gettext as _
from django.conf import settings

default_layouts = {}
default_layouts["address"] = (
    [],
    [
        {
            "key": "name",
            "field": "CharField",
            "max_length": 512
        },
        {
            "key": "place",
            "field": "CharField",
            "max_length": 512
        },
        {
            "key": "street_number",
            "field": "CharField",
            "max_length": 10,
            "required": False
        },
        {
            "key": "city",
            "field": "CharField",
            "max_length": 256
        },
        {
            "key": "post_code",
            "field": "CharField",
            "max_length": 20,
            "required": False
        },
        {
            "key": "country_area",
            "field": "CharField",
            "max_length": 256,
            "required": False
        },
        {
            "key": "country_code",
            "field": "CharField",
            "min_length": 2,
            "max_length": 3
        }
    ]
)
default_layouts["person1"] = (
    [],
    [
        {
            "key": "address",
            "field": "LayoutRefField",
            "valid_layouts": ["address"]
        },
        {
            "key": "title",
            "field": "CharField",
            "max_length": 10,
            "required": False
        },
        {
            "key": "first_name",
            "field": "CharField",
            "max_length": 255
        },
        {
            "key": "extra_names",
            "field": "CharField",
            "max_length": 255,
            "required": False
        },
        {
            "key": "last_name",
            "field": "CharField",
            "max_length": 255,
            "required": False
        }
    ]
)
default_layouts["emergency"] = (
    [],
    [
        {
            "key": "address",
            "field": "LayoutRefField",
            "valid_layouts": ["address"],
            "required": False
        },
        {
            "key": "contacts",
            "field": "TextareaField",
        },
        {
            "key": "bgender",
            "label": _("Biologic Gender"),
            "field": "ChoiceField",
            "choices": [
                ("male", _("male")),
                ("female", _("female")),
                ("both", _("both")),
                ("none", _("none")),
            ],
            "required": False
        },
        {
            "key": "bloodgroup",
            "label": _("Blood Group"),
            "field": "ChoiceField",
            "choices": [
                ("A", "A"),
                ("B", "B"),
                ("AB", "AB"),
                ("0", "0"),
            ],
            "required": False
        },
        {
            "key": "rhesus_factor",
            "label": _("Rhesus Factor"),
            "field": "ChoiceField",
            "choices": [
                ("rh+", "Rh+"),
                ("rh-", "Rh-"),
            ],
            "required": False
        },
        {
            "key": "health_problems",
            "label": _("Health Problems"),
            "field": "SelectMultiple",
            "choices": [
                ("heart", _("Heart")),
                ("diabetes", _("Diabetes")),
                ("lung", _("Lung")),
                ("dementia", _("Dementia")),
                ("social", _("Social")),
                ("phobia", _("Phobias")),
            ],
            "required": False
        },
        {
            "key": "organ_donations",
            "label": _("Organ donations in case of death"),
            "field": "SelectMultiple",
            "choices": [
                ("all", _("All organs")),
                ("special", _("Special Organs")),
                ("contacts", _("Contacts can decide")),
                ("none", _("None")),
            ],
            "required": False
        },
        {
            "key": "organs",
            "label": _('In case of: "Special Organs", which?'),
            "field": "TextField",
            "required": False
        }
    ]
)


def initialize_layouts(apps=None):
    if not apps:
        from django.apps import apps
    TagLayout = apps.get_model("spider_tags", "TagLayout")
    layouts = default_layouts.copy()
    for l in getattr(settings, "TAG_LAYOUT_PATHES", []):
        module, name = l.rsplit(".", 1)
        layouts.update(getattr(__import__(module), name))
    for name, val in layouts.items():
        verifiers, layout = val
        tag_layout = TagLayout.objects.get_or_create(
            defaults={
                "layout": layout, "default_verifiers": verifiers
            }, name=name
        )[0]
        if tag_layout.layout != layout or \
           tag_layout.default_verifiers != verifiers:
            tag_layout.layout = layout
            tag_layout.default_verifiers = verifiers
            tag_layout.save()
    invalid_models = TagLayout.objects.exclude(
        name__in=layouts.keys(), usertag=None
    )
    if invalid_models.exists():
        print("Invalid layouts, please update or remove them:",
              [t.name for t in invalid_models])
