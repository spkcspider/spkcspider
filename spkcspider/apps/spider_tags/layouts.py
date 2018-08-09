

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
default_layouts["person"] = (
    [],
    [
        {
            "key": "address",
            "field": "LayoutRefField",
            "valid_layouts": ["address"]
        },
        {
            "key": "gender",
            "field": "ChoiceField"
        }
    ]
)


def initialize_layouts(apps=None):
    if not apps:
        from django.apps import apps
    TagLayout = apps.get_model("spider_tags", "TagLayout")
    for name, val in default_layouts.items():
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
        name__in=default_layouts.keys(), owner=None
    )
    if invalid_models.exists():
        print("Invalid content, please update or remove them:",
              [t.code for t in invalid_models])
