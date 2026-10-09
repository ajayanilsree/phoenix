from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import Service, ServiceCategory
from .richtext import sanitize_rich_text, word_count


class ServiceCategoryForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        label="Category Name",
        required=True,
        strip=True,
        widget=forms.TextInput(attrs={"placeholder": "Enter category name"}),
        error_messages={"required": "Category name is required."},
    )

    def __init__(self, *args, instance=None, parent=None, **kwargs):
        self.instance = instance
        self.parent = parent if parent is not None else getattr(instance, "parent", None)
        super().__init__(*args, **kwargs)
        if instance:
            self.fields["name"].initial = instance.name

    def clean_name(self):
        name = self.cleaned_data["name"]
        siblings = ServiceCategory.objects.filter(parent=self.parent, name__iexact=name)
        if self.instance:
            siblings = siblings.exclude(pk=self.instance.pk)
        if siblings.exists():
            raise ValidationError("A category with this name already exists here.")
        return name

    def save(self):
        category = self.instance or ServiceCategory(parent=self.parent, is_active=True)
        category.name = self.cleaned_data["name"]
        if not category.pk:
            base_slug = slugify(category.name) or "service-category"
            category.slug = base_slug
            suffix = 2
            while ServiceCategory.objects.filter(slug=category.slug).exists():
                category.slug = f"{base_slug}-{suffix}"
                suffix += 1
        category.save()
        return category


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["title", "category", "subcategory", "description", "consultation_fee", "is_active"]
        labels = {"title": "Service Name", "consultation_fee": "Consultation Fees (₹)"}
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter service name"}),
            "description": forms.Textarea(attrs={"rows": 10, "data-rich-text-source": "true"}),
            "consultation_fee": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get("description") is None:
            self.initial["description"] = ""
        self.fields["category"].queryset = ServiceCategory.objects.filter(parent__isnull=True, is_active=True).order_by("sort_order", "name")
        self.fields["subcategory"].queryset = ServiceCategory.objects.filter(parent__isnull=False, is_active=True).select_related("parent").order_by("parent__sort_order", "sort_order", "name")
        self.fields["subcategory"].required = False
        self.fields["is_active"].label = "Active"

    def clean_description(self):
        description, _ = sanitize_rich_text(self.cleaned_data["description"])
        if word_count(description) > 500:
            raise ValidationError("Description cannot exceed 500 words.")
        if not description:
            raise ValidationError("Description is required.")
        return description

    def clean_consultation_fee(self):
        fee = self.cleaned_data["consultation_fee"]
        if fee <= 0:
            raise ValidationError("Consultation fee must be greater than zero.")
        return fee

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")
        if category and not subcategory and (not self.instance or not self.instance.pk) and category.children.filter(is_active=True).exists():
            self.add_error("subcategory", "Choose a subcategory for this service.")
        if subcategory and category and subcategory.parent_id != category.id:
            self.add_error("subcategory", "Choose a subcategory belonging to the selected category.")
        return cleaned

    def save(self, commit=True):
        service = super().save(commit=False)
        if not service.slug or self.instance.title != service.title:
            base_slug = slugify(service.title) or "service"
            service.slug = base_slug
            suffix = 2
            while Service.objects.filter(slug=service.slug).exclude(pk=service.pk).exists():
                service.slug = f"{base_slug}-{suffix}"
                suffix += 1
        if commit:
            service.save()
        return service
