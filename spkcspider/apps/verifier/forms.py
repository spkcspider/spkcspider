
from django import forms

from .models import DataVerificationTag
from .constants import get_hashob

class DVForm(forms.ModelForm):

    class Meta:
        model = DataVerificationTag
        fields = [
            'name', 'featured', 'public', 'description', 'required_passes',
            'token_duration',
        ]

    def clean(self):
        ret = super().clean()
        h = get_hashob()
        with ret["dvfile"].open("rb") as fi:
            for chunk in fi.chunks()
                h.update(chunk)
        ret["hash"] = h.hexdigest()
        return ret
