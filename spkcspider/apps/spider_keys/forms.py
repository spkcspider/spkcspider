__all__ = ["KeyForm", "AnchorServerForm", "AnchorKeyForm"]
# "AnchorGovForm"


from django import forms
# from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from .models import PublicKey, AnchorServer, AnchorKey
# AnchorGov, ID_VERIFIERS


class KeyForm(forms.ModelForm):
    class Meta:
        model = PublicKey
        fields = ['key', 'note']

    def clean_key(self):
        _ = gettext
        data = self.cleaned_data['key'].strip()
        if data == "":
            raise forms.ValidationError(
                _('Empty Key'),
                code="empty"
            )
        if "PRIVATE" in data.upper():
            raise forms.ValidationError(
                _('Private Key')
            )
        return data


class AnchorServerForm(forms.ModelForm):
    identifier = forms.CharField(disabled=True)
    scope = ""

    class Meta:
        model = AnchorServer
        fields = []

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["identifier"]

    def clean(self):
        self.cleaned_data["type"] = "server"
        self.cleaned_data["format"] = "server_{identifier}"
        return self.cleaned_data


class AnchorKeyForm(forms.ModelForm):
    identifier = forms.CharField(disabled=True)
    scope = ""

    class Meta:
        model = AnchorKey
        fields = ['key', 'signature']

    def __init__(self, scope, **kwargs):
        self.scope = scope
        super().__init__(**kwargs)
        if self.scope == "add":
            del self.fields["signature"]

    def clean(self):
        self.cleaned_data["type"] = "key"
        self.cleaned_data["format"] = "key_{hash}"
        return self.cleaned_data


# class AnchorGovForm(forms.ModelForm):
#    identifier = forms.CharField(disabled=True, widget=forms.HiddenInput())
#    scope = ""
#
#    class Meta:
#        model = AnchorGov
#        fields = ['idtype', 'token']
#
#    def __init__(self, scope, **kwargs):
#        self.scope = scope
#        super().__init__(**kwargs)
#
#    def clean(self):
#        self.cleaned_data["type"] = "gov"
#        self.cleaned_data["identifier"] = self.instance.get_identifier()
#        self.cleaned_data["format"] = "gov_{verifier}_{token}"
#        if self.scope not in ["add", "update"]:
#            self.cleaned_data["verifier"] = ID_VERIFIERS[self.idtype]
#        del self.cleaned_data["idtype"]
#        return self.cleaned_data
