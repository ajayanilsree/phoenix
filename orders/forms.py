from django import forms
from django.core.exceptions import ValidationError

from .models import Address


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ["full_name", "phone", "line1", "line2", "city", "district", "state", "postal_code", "country"]
        labels = {
            "line1": "Address Line 1",
            "line2": "Address Line 2",
            "postal_code": "Postal Code / PIN Code",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["district"].required = True
        self.fields["country"].initial = self.fields["country"].initial or "India"

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if len(full_name) < 2:
            raise ValidationError("Enter a valid full name.")
        return full_name

    def clean_phone(self):
        phone = " ".join(self.cleaned_data["phone"].split())
        compact = phone.replace(" ", "").replace("-", "")
        if compact.startswith("+"):
            digits = compact[1:]
        else:
            digits = compact
        if not digits.isdigit() or len(digits) < 10 or len(digits) > 13:
            raise ValidationError("Enter a valid phone number.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data["postal_code"].strip().replace(" ", "")
        if not postal_code.isdigit() or len(postal_code) != 6:
            raise ValidationError("Enter a valid 6-digit PIN code.")
        return postal_code

    def clean_country(self):
        return self.cleaned_data["country"].strip() or "India"


class CustomerAddressForm(AddressForm):
    pass


class CheckoutAddressForm(AddressForm):
    use_saved_delivery = forms.BooleanField(required=False, label="Use my saved delivery address")
    use_billing_address = forms.BooleanField(required=False, label="Use my billing address as the delivery address")
    save_delivery_address = forms.BooleanField(required=False, label="Save this as my default delivery address")


class AgentPromoForm(forms.Form):
    promo_code = forms.CharField(
        label="Have a promo code?",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Enter promo code"}),
    )

    def clean_promo_code(self):
        return self.cleaned_data["promo_code"].strip().upper()
