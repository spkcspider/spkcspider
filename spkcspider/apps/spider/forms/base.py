
__all__ = ["DataContentForm"]

from django import forms


class DataContentForm(forms.Form):

    free_fields = {}
    quota_fields = {}

    def __init__(self, instance, initial=None, **kwargs):
        if initial is None:
            initial = {}
        super().__init__(**kwargs)
        self.initial.update(instance.free_data)
        self.initial.update(instance.quota_data)
        self.initial.update(initial)

    def get_prepared_attachements(self):
        return {}

    def save(self, commit=True):
        ret = self.instance
        ret.prepared_attachements = self.get_prepared_attachements()
        for key, default in self.free_fields.items():
            if key in self.fields:
                ret.free_data[key] = self.cleaned_data.get(key, default)
                if callable(ret.free_data[key]):
                    ret.free_data[key] = ret.free_data[key]()
        for key, default in self.quota_fields.items():
            if key in self.fields:
                ret.quota_data[key] = self.cleaned_data.get(key, default)
                if callable(ret.quota_data[key]):
                    ret.quota_data[key] = ret.quota_data[key]()
        if commit:
            ret.save()
        return ret
