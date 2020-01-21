
__all__ = ["DataContentForm"]

from django import forms


class DataContentForm(forms.Form):
    instance = None
    # TODO: document
    free_fields = {}
    # TODO: document
    quota_fields = {}

    def __init__(self, instance, initial=None, **kwargs):
        super().__init__(**kwargs)
        self.instance = instance
        self.initial.update(instance.free_data)
        self.initial.update(instance.quota_data)
        if initial is not None:
            self.initial.update(initial)

    def prepare_instance(self):
        instance = self.instance
        instance.prepared_attachements = self.get_prepared_attachements()
        # don't read from initial, for allowing non-saved initial values
        for key, default in self.free_fields.items():
            field = self.fields.get(key, None)
            if field:
                instance.free_data[key] = self.cleaned_data.get(key, default)
                if callable(instance.free_data[key]):
                    instance.free_data[key] = instance.free_data[key]()
        for key, default in self.quota_fields.items():
            field = self.fields.get(key, None)
            if field:
                instance.quota_data[key] = self.cleaned_data.get(key, default)
                if callable(instance.quota_data[key]):
                    instance.quota_data[key] = instance.quota_data[key]()
        return instance

    def get_prepared_attachements(self):
        return {}

    def clean(self):
        self.instance.full_clean()
        return super().clean()

    def save_m2m(self):
        # stub
        pass

    def save(self, commit=True):
        ret = self.prepare_instance()
        if commit:
            ret.save()
        return ret
