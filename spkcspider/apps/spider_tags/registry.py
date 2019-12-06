__all__ = ["FieldRegistry", "LayoutRegistry", "fields", "layouts"]

from spkcspider.apps.spider.registry import Registry


class FieldRegistry(Registry):
    attr_path = "spider_fields_path"

    def __setitem__(self, key, value):
        assert value, "invalid value type %s" % type(value)
        super().__setitem__(key, value)


class LayoutRegistry(Registry):
    attr_path = "spider_layouts_path"

    def __setitem__(self, key, value):
        assert value, "invalid value type %s" % type(value)
        super().__setitem__(key, value)

    def initialize(self):
        from django.apps import apps
        TagLayout = apps.get_model("spider_tags", "TagLayout")
        # iterate over unionized layouts
        for name, layout_dic in self.items():
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


fields = FieldRegistry()
layouts = LayoutRegistry()
