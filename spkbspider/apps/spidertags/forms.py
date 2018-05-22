from django import forms
from django.utils.translation import gettext_lazy as _


import base64

class SpiderTagForm(forms.Form):
    usercomponent = None
    class Meta:
        model = "spidertags.SpiderTag"
        fields = ['url']

    def __init__(self, *args, **kwargs):
        self.usercomponent = kwargs.pop("usercomponent")
        super().__init__(*args, **kwargs)

    def get_info(self):
        return "verifiers=%s;tag=%s;" % (base64.b64_urlencode(self.cleaned_data["url"]), self.cleaned_data["tagtype"])

    def is_valid(self):
        if not super().is_valid(): return False
        # check that usercomponent contains only one Broker with url
        burl = base64.b64_urlencode(self.cleaned_data["url"])
        if self.instance.associated and self.instance.associated.usercomponent == self.usercomponent:
            maxamount = 1
        else:
            maxamount = 0
        return len(SpiderTag.objects.filter(info__contains="type=Tag;").filter(info__contains="burl=%s"% burl)) <= maxamount


    def clean(self):
        super().clean()
