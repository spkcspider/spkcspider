from django import forms
from django.utils.translation import ugettext_lazy as _


import base64

class BaseBrokerForm(forms.ModelForm):
    def get_info(self, uc):
        return "burl=%s;broker=%s;" % (base64.b64_urlencode(self.cleaned_data["url"]), self.cleaned_data["brokertype"])

class BrokerForm(BaseBrokerForm):
    from .models import Broker
    class Meta:
        model = Broker
        fields = ['url']


class IBrokerForm(BaseBrokerForm):
    from .models import Broker
    class Meta:
        model = Broker
        fields = ['url', 'brokerdata']
