from django import forms
from django.utils.translation import ugettext_lazy as _


import base64

class BrokerForm(forms.Form):
    from .models import Broker
    usercomponent = None
    class Meta:
        model = Broker
        fields = ['url']

    def __init__(self, *args, **kwargs):
        self.usercomponent = kwargs.pop("usercomponent")
        super().__init__(*args, **kwargs)

    def get_info(self):
        return "burl=%s;broker=%s;" % (base64.b64_urlencode(self.cleaned_data["url"]), self.cleaned_data["brokertype"])

    def is_valid(self):
        return False if not super().is_valid()
        # check that usercomponent contains only one Broker with url
        burl = base64.b64_urlencode(self.cleaned_data["url"])
        if self.instance.associated and self.instance.associated.usercomponent = self.usercomponent:
            maxamount = 1
        else:
            maxamount = 0
        return len(Broker.objects.filter(info__contains="type=Broker;").filter(info__contains="burl=%s"% burl)) <= maxamount


    def clean(self):
        super().clean()
