__all__ = ("default_layouts", "initialize_layouts")

from django.utils.translation import gettext_noop as _
from django.conf import settings

default_layouts = {}
default_layouts["address"] = {
    "layout": [
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
}

default_layouts["person_official"] = {
    "layout": [
        {
            "key": "address",
            "label": _("Address"),
            "localize": True,
            "field": "UserContentRefField",
            "modelname": "spider_tags.SpiderTag",
            "limit_choices_to": {
                "layout__name__in": ["address"]
            },
        },
        {
            "key": "title",
            "label": _("Titles"),
            "localize": True,
            "field": "CharField",
            "max_length": 20,
            "required": False
        },
        {
            "key": "first_name",
            "label": _("First Name"),
            "localize": True,
            "field": "CharField",
            "max_length": 255
        },
        {
            "key": "extra_names",
            "label": _("Extra Name"),
            "localize": True,
            "field": "CharField",
            "max_length": 255,
            "required": False
        },
        {
            "key": "last_name",
            "label": _("Last Name"),
            "localize": True,
            "field": "CharField",
            "max_length": 255,
            "required": False
        },
        {
            "key": "iddocs",
            "label": _("ID Documents"),
            "localize": True,
            "field": "MultipleUserContentRefField",
            "modelname": "spider_filets.FileFilet",
            "required": False
        },
        {
            "key": "anchor",
            "field": "AnchorField",
            "required": False
        }
    ]
}

default_layouts["emergency"] = {
    "layout": [
        {
            "key": "address",
            "field": "UserContentRefField",
            "modelname": "spider_tags.SpiderTag",
            "limit_choices_to": {
                "layout__name__in": ["address"]
            },
            "required": False
        },
        {
            "key": "contacts",
            "initial": "",
            "field": "TextareaField",
            "required": False
        },
        {
            "key": "bgender",
            "label": _("Biologic Gender"),
            "localize": True,
            "field": "LocalizedChoiceField",
            "choices": [
                ("", _("")),
                ("male", _("male")),
                ("female", _("female")),
                ("other", _("other")),
            ],
            "required": False
        },
        {
            "key": "bloodgroup",
            "label": _("Blood Group"),
            "localize": True,
            "field": "ChoiceField",
            "choices": [
                ("", ""),
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
            "localize": True,
            "field": "ChoiceField",
            "choices": [
                ("", ""),
                ("rh+", "Rh+"),
                ("rh-", "Rh-"),
            ],
            "required": False
        },
        {
            "key": "health_problems",
            "label": _("Health Problems"),
            "localize": True,
            "field": "MultipleLocalizedChoiceField",
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
            "localize": True,
            "field": "LocalizedChoiceField",
            "choices": [
                ("", ""),
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
            "field": "TextareaField",
            "required": False
        }
    ]
}


def initialize_layouts(apps=None):
    if not apps:
        from django.apps import apps
    TagLayout = apps.get_model("spider_tags", "TagLayout")
    layouts = default_layouts.copy()
    # create union from all layouts
    for l in getattr(settings, "TAG_LAYOUT_PATHES", []):
        module, name = l.rsplit(".", 1)
        layouts.update(getattr(__import__(module), name))
    # iterate over unionized layouts
    for name, layout_dic in layouts.items():
        tag_layout = TagLayout.objects.get_or_create(
            defaults=layout_dic, name=name
        )[0]
        has_changed = False
        # check attributes of model
        for layout_attr, value in layout_dic.items():
            if getattr(tag_layout, layout_attr) != value:
                # layout change detected, update and mark for saving
                setattr(tag_layout, layout_attr, value)
                has_changed = True

        if has_changed:
            tag_layout.save()
    invalid_models = TagLayout.objects.exclude(
        name__in=layouts.keys(), usertag=None
    )
    if invalid_models.exists():
        print("Invalid layouts, please update or remove them:",
              [t.name for t in invalid_models])
