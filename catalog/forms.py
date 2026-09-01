from django import forms

from .models import ProductReview


class ProductReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(str(value), str(value)) for value in range(1, 6)],
        widget=forms.RadioSelect,
        label="Your rating",
        error_messages={"required": "Please select a star rating."},
    )

    class Meta:
        model = ProductReview
        fields = ["rating", "review"]
        labels = {"review": "Your review"}
        widgets = {
            "review": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                    "placeholder": "Share your experience with this product...",
                }
            ),
        }

    def clean_review(self):
        value = self.cleaned_data["review"].strip()
        if len(value) < 3:
            raise forms.ValidationError("Review must be at least 3 characters.")
        return value
