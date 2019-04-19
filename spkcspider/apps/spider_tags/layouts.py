__all__ = ("default_layouts", "initialize_layouts")

from django.utils.translation import gettext_noop as _
from spkcspider.apps.spider.helpers import extract_app_dicts

default_layouts = {}
default_layouts["address"] = {
    "description": _(
        "An universal address.\n"
        "Can be used for persons and companies."
    ),
    "layout": [
        {
            "key": "name",
            "localize": True,
            "label": _("Name"),
            "field": "CharField",
            "max_length": 512
        },
        {
            "key": "place",
            "localize": True,
            "label": _("Street/Place"),
            "field": "CharField",
            "max_length": 512
        },
        {
            "key": "street_number",
            "localize": True,
            "label": _("Street Number"),
            "field": "CharField",
            "max_length": 10,
            "required": False
        },
        {
            "key": "city",
            "localize": True,
            "label": _("City"),
            "field": "CharField",
            "max_length": 256
        },
        {
            "key": "post_code",
            "localize": True,
            "label": _("Post Code"),
            "field": "CharField",
            "max_length": 20,
            "required": False
        },
        {
            "key": "country_area",
            "localize": True,
            "label": _("Country Area"),
            "field": "CharField",
            "max_length": 256,
            "required": False
        },
        {
            "key": "country_code",
            "localize": True,
            "label": _("Country Code"),
            "field": "CharField",
            "min_length": 2,
            "max_length": 3
        }
    ]
}

default_layouts["person_official"] = {
    "description": _(
        "An description of a person.\n"
        "For e.g. shopping or contracts"
    ),
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


default_layouts["work"] = {
    "description": _(
        "Basic specifications of a work."
    ),
    "layout": [
        {
            "key": "worker",
            "label": _("Worker"),
            "localize": True,
            "field": "UserContentRefField",
            "modelname": "spider_tags.SpiderTag",
            "limit_choices_to": {
                "layout__name__in": ["person_official"]
            },
        },
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
    ]
}


default_layouts["emergency"] = {
    "description": _(
        "Emergency information."
    ),
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
            "required": False
        },
        {
            "key": "contacts",
            "label": _("Contacts"),
            "localize": True,
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
                ("", ""),
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
            "localize": True,
            "label": _('In case of: "Special Organs", which?'),
            "field": "TextareaField",
            "required": False
        }
    ]
}


default_layouts["license"] = {
    "description": _(
        "License."
    ),
    "layout": [
        {
            "key": "license_name",
            "label": _("Name"),
            "localize": True,
            "field": "CharField",
            "required": True
        },
        {
            "key": "license_body",
            "label": _("License"),
            "localize": True,
            "initial": "",
            "field": "TextareaField",
            "required": True
        },
    ]
}


def initialize_layouts(apps=None):
    if not apps:
        from django.apps import apps
    TagLayout = apps.get_model("spider_tags", "TagLayout")
    layouts = default_layouts.copy()
    # create union from all layouts
    for app in apps.get_app_configs():
        layouts.update(
            extract_app_dicts(app, "spider_tag_layouts")
        )
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
