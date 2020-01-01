__all__ = [
    "Registry", "ProtectionRegistry", "ContentRegistry", "FeatureUrlsRegistry",
    "ContentDeletionPeriodRegistry",
    "protections", "contents", "feature_urls", "content_deletion_periods"
]

import logging

from django.shortcuts import resolve_url

from spkcspider.constants import ActionUrl

logger = logging.getLogger(__name__)


class Registry(object):
    key_type_registry = {
        "str": lambda x: x
    }
    attr_path = None

    _unchecked_apps = None
    _populated = False
    _registry = None

    find_func = None

    def __init__(self):
        self._unchecked_apps = set()
        self._registry = {}

    def __getitem__(self, ob):
        key = self.get_key(ob)
        if key not in self._registry:
            find_func = self.find_func or self.generate_find_func
            self._registry[key] = find_func(key)
        return self._registry[key]

    def __setitem__(self, key, value):
        self._registry[key] = value

    def __contains__(self, ob):
        return self.get_key(ob) in self._registry

    def __getattr__(self, attr):
        return getattr(self._registry, attr)

    def get_key(self, ob):
        return self.key_type_registry[type(ob).__name__](ob)

    def generate_find_func(self, key):
        """ generate generator based find function """
        from django.apps import apps
        from importlib import import_module
        self._unchecked_apps.update(apps.get_app_configs())

        def find_func(key):
            if self._unchecked_apps:
                checked = []
                for app in self._unchecked_apps:
                    if hasattr(app, self.attr_path):
                        import_module(
                            getattr(app, self.attr_path),
                            app.name
                        )
                    checked.append(app)
                    if key in self:
                        break
                self._unchecked_apps.difference_update(checked)
            return self[key]
        self.find_func = find_func
        return self.find_func(key)

    def populate(self):
        """ Populate all possible content, required for iterations """
        from importlib import import_module
        from django.apps import apps
        for app in apps.get_app_configs():
            if hasattr(app, self.attr_path):
                import_module(
                    getattr(app, self.attr_path),
                    app.name
                )
        self._populated = True

    def keys(self):
        if not self._populated:
            self.populate()
        return self._registry.keys()

    def values(self):
        if not self._populated:
            self.populate()
        return self._registry.values()

    def items(self):
        if not self._populated:
            self.populate()
        return self._registry.items()


class ProtectionRegistry(Registry):
    _unchecked_apps = None
    attr_path = "spider_protections_path"

    def __init__(self):
        self.key_type_registry = {
            "str": lambda x: x,
            "Protection": lambda x: x.code,
            "AssignedProtection": lambda x: x.protection.code
        }
        super().__init__()

    def __setitem__(self, key, value):
        if key in self:
            raise Exception("Already exists")
        assert value, "invalid value type %s" % type(value)
        super().__setitem__(key, value)

    def initialize(self):
        from spkcspider.constants import ProtectionStateType
        from django.apps import apps
        UserComponent = apps.get_model("spider_base", "UserComponent")
        AssignedProtection = apps.get_model(
            "spider_base",
            "AssignedProtection"
        )
        ProtectionModel = apps.get_model("spider_base", "Protection")
        # auto initializes
        for code, val in self.items():
            ret = ProtectionModel.objects.get_or_create(
                defaults={"ptype": val.ptype}, code=code
            )[0]
            if ret.ptype != val.ptype:
                ret.ptype = val.ptype
                ret.save()

        login = ProtectionModel.objects.filter(code="login").first()
        if login:
            for uc in UserComponent.objects.filter(name="index"):
                assignedprotection = AssignedProtection.objects.get_or_create(
                    defaults={"state": ProtectionStateType.enabled},
                    usercomponent=uc, protection=login
                )[0]
                if assignedprotection.state == ProtectionStateType.disabled:
                    assignedprotection.state = ProtectionStateType.enabled
                    assignedprotection.save()

        invalid_models = ProtectionModel.objects.exclude(
            code__in=self.keys()
        )
        if invalid_models.exists():
            print(
                "Invalid protections, please update or remove them:",
                [t.code for t in invalid_models]
            )


class ContentRegistry(Registry):
    # updated attributes of ContentVariant
    _attribute_list = ["name", "ctype", "strength"]

    def __init__(self):
        self.key_type_registry = {
            "str": lambda x: x,
            "ContentVariant": lambda x: x.code,
            "AssignedContent": lambda x: x.ctype.code
        }
        super().__init__()

    def __setitem__(self, key, value):
        if key in self:
            raise Exception("Already exists")
        assert value, "invalid value type %s" % type(value)
        super().__setitem__(key, value)

    def generate_find_func(self, key):
        if not self._populated:
            self.populate()

        def find_func(key):
            return self[key]
        self.find_func = find_func
        return self.find_func(key)

    def populate(self):
        from django.apps import apps
        apps.populate()
        self._populated = True

    def initialize(self):
        from spkcspider.constants import essential_contents, VariantType
        from django.db import models, transaction
        from django.db.utils import IntegrityError
        from django.apps import apps
        from .abstract_models.contents import forbidden_names
        ContentVariant = apps.get_model("spider_base", "ContentVariant")

        all_content = models.Q()
        valid_for = {}

        diff = essential_contents.difference(
            self.keys()
        )
        if diff:
            logger.warning(
                "Missing essential contents: %s" % diff
            )

        for code, val in self.items():
            appearances = val.appearances
            if callable(appearances):
                appearances = appearances()
            assert appearances is not None, "missing appearances: %s" % code

            # update name if only one name exists
            update = (len(appearances) == 1)

            for attr_dict in appearances:
                require_save = False
                assert attr_dict["name"] not in forbidden_names, \
                    "Forbidden content name: %s" % attr_dict["name"]
                attr_dict = attr_dict.copy()
                _v_for = attr_dict.pop("valid_feature_for", None)
                try:
                    with transaction.atomic():
                        if update:
                            variant = ContentVariant.objects.get_or_create(
                                defaults=attr_dict, code=code
                            )[0]
                        else:
                            variant = ContentVariant.objects.get_or_create(
                                defaults=attr_dict, code=code,
                                name=attr_dict["name"]
                            )[0]

                except IntegrityError:
                    # renamed model = code changed
                    variant = ContentVariant.objects.get(
                        name=attr_dict["name"]
                    )
                    variant.code = code
                    require_save = True

                if _v_for:
                    if _v_for == "*":
                        valid_for[attr_dict["name"]] = (variant, set("*"))
                    else:
                        valid_for[attr_dict["name"]] = (variant, set(_v_for))
                elif VariantType.content_feature in variant.ctype:
                    logger.warning(
                        "%s defines content_feature but defines no "
                        "\"valid_feature_for\"", variant.name
                    )

                for key in self._attribute_list:
                    val = attr_dict.get(
                        key, variant._meta.get_field(key).get_default()
                    )
                    if getattr(variant, key) != val:
                        setattr(variant, key, val)
                        require_save = True
                if require_save:
                    variant.save()
                all_content |= models.Q(name=attr_dict["name"], code=code)
        for val in valid_for.values():
            try:
                # try first to exclude by stripping "*" and checking error
                val[1].remove("*")
                val[0].valid_feature_for.set(ContentVariant.objects.exclude(
                    name__in=val[1]
                ))
            except KeyError:
                val[0].valid_feature_for.set(ContentVariant.objects.filter(
                    name__in=val[1]
                ))

        invalid_models = ContentVariant.objects.exclude(all_content)
        if invalid_models.exists():
            print(
                "Invalid content, please update or remove them:",
                ["\"{}\":{}".format(t.code, t.name) for t in invalid_models]
            )


class FeatureUrlsRegistry(Registry):
    contentRegistry = None
    default_actions = None

    def __init__(self, contentRegistry):
        self.contentRegistry = contentRegistry
        self.default_actions = {}
        self.key_type_registry = {
            "tuple": lambda x: x,
            "list": tuple,
            "ContentVariant": lambda x: (x.code, x.name),
            "AssignedContent": lambda x: (x.ctype.code, x.ctype.name)
        }
        super().__init__()

    def generate_find_func(self, key):
        from django.conf import settings
        self.default_actions["delete-token"] = \
            "spider_base:token-delete-request"
        if getattr(settings, "DOMAINAUTH_URL", None):
            self.default_actions["domainauth-url"] = settings.DOMAINAUTH_URL

        def find_func(key):
            self[key] = frozenset(map(
                lambda x: ActionUrl(x[0], resolve_url(x[1])),
                self.contentRegistry[key[0]].feature_urls(key[1])
            ))
            return self[key]
        self.find_func = find_func
        return self.find_func(key)

    def populate(self):
        for code, content in self.contentRegistry.items():
            for appearance in content.appearances:
                # calls generate_find_func if required
                self[(code, appearance["name"])]
        self._populated = True


class ContentDeletionPeriodRegistry(Registry):
    contentRegistry = None

    def __init__(self, contentRegistry):
        self.contentRegistry = contentRegistry
        self.key_type_registry = {
            "tuple": lambda x: x,
            "ContentVariant": lambda x: (x.code, x.name),
            "AssignedContent": lambda x: (x.ctype.code, x.ctype.name)
        }
        super().__init__()

    def generate_find_func(self, key):
        from django.conf import settings
        self.update(
            getattr(
                settings, "SPIDER_CONTENTS_DELETION_PERIODS", {}
            )
        )

        def find_func(key):
            deletion_period = self.contentRegistry[key[0]].deletion_period
            if callable(deletion_period):
                self[key] = deletion_period(key[1])
            else:
                self[key] = deletion_period
            return self[key]
        self.find_func = find_func
        return self.find_func(key)

    def populate(self):
        for code, content in self.contentRegistry.items():
            for appearance in content.appearances:
                # calls generate_find_func if required
                self[(code, appearance["name"])]
        self._populated = True


protections = ProtectionRegistry()
contents = ContentRegistry()
feature_urls = FeatureUrlsRegistry(contents)
content_deletion_periods = ContentDeletionPeriodRegistry(contents)
