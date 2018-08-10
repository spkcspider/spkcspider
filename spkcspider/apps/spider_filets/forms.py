from django import forms

from .models import FileFilet, TextFilet


class FileForm(forms.ModelForm):
    class Meta:
        model = FileFilet
        fields = ['file', 'name']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        if self.instance and self.instance.is_owner(user):
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False

    def clean(self):
        ret = super().clean()
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'non_public_edit']

    def __init__(self, user=None, source=None, **kwargs):
        super().__init__(**kwargs)
        if self.instance and self.instance.is_owner(user):
            return

        self.fields["name"].editable = False
        del self.fields["non_public_edit"]

        self.fields["text"].editable = False

        if self.instance.non_public_edit:
            allow_edit = False
            if source and not source.associated.usercomponent.public:
                allow_edit = True
            elif (
                    not source and
                    not self.instance.associated.usercomponent.public
                 ):
                allow_edit = True

            if allow_edit:
                self.fields["text"].editable = True
