__all__ = [
    "LinkForm", "TravelProtectionForm"
]

from django import forms

from ..models import LinkContent, TravelProtection


class LinkForm(forms.ModelForm):

    class Meta:
        model = LinkContent
        fields = ['content']

    def __init__(self, uc, **kwargs):
        super().__init__(**kwargs)
        q = self.fields["content"].queryset
        travel = TravelProtection.objects.get_active()
        self.fields["content"].queryset = q.filter(
            strength__lte=uc.strength
        ).exclude(usercomponent__travel_protected__in=travel)


class TravelProtectionForm(forms.ModelForm):
    uc = None
    is_fake = None

    class Meta:
        model = TravelProtection
        fields = [
            "active", "start", "stop", "self_protection", "login_protection",
            "disallow"
        ]

    def __init__(self, uc, is_fake, **kwargs):
        super().__init__(**kwargs)
        self.uc = uc
        self.is_fake = is_fake
        # elif self.travel_protection.is_active:
        #    for f in self.fields:
        #        f.disabled = True
