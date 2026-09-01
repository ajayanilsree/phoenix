from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from accounts.models import AgentProfile, StaffProfile, UserProfile
from catalog.models import Category, Product
from inventory.models import InventoryRecord
from orders.models import Order


def unique_slug_for(model, value, instance=None):
    base_slug = slugify(value) or "item"
    slug = base_slug
    counter = 2
    queryset = model.objects.filter(slug=slug)
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
        queryset = model.objects.filter(slug=slug)
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
    return slug


class ProductManageForm(forms.ModelForm):
    stock = forms.IntegerField(min_value=0, required=False, initial=0)
    low_stock_threshold = forms.IntegerField(min_value=0, required=False, initial=5)

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "category",
            "subcategory",
            "full_description",
            "compare_at_price",
            "price",
            "unit_type",
            "size",
            "thickness",
            "colour",
            "finish",
            "features",
            "applications",
        ]
        labels = {
            "full_description": "Product Description",
            "compare_at_price": "Original Price",
            "price": "Discount Price / Selling Price",
        }
        widgets = {
            "full_description": forms.Textarea(attrs={"rows": 5}),
            "features": forms.Textarea(attrs={"rows": 3}),
            "applications": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True, parent__isnull=True).order_by("sort_order", "name")
        self.fields["subcategory"].queryset = Category.objects.filter(is_active=True, parent__isnull=False).select_related("parent").order_by("parent__sort_order", "sort_order", "name")
        self.fields["subcategory"].required = True
        if self.instance and self.instance.pk:
            inventory = getattr(self.instance, "inventory", None)
            if inventory:
                self.fields["stock"].initial = inventory.current_stock
                self.fields["low_stock_threshold"].initial = inventory.low_stock_threshold

    def clean(self):
        cleaned = super().clean()
        original = cleaned.get("compare_at_price")
        selling = cleaned.get("price")
        if selling is not None and selling < Decimal("0.00"):
            self.add_error("price", "Discount/selling price cannot be negative.")
        if original is not None and original <= Decimal("0.00"):
            self.add_error("compare_at_price", "Original price must be greater than zero.")
        if original is not None and selling is not None and selling > original:
            self.add_error("price", "Discount price must be less than or equal to original price.")
        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")
        if category and subcategory and subcategory.parent_id != category.id:
            self.add_error("subcategory", "Select a subcategory that belongs to the selected category.")
        return cleaned

    def save(self, commit=True):
        product = super().save(commit=False)
        if not product.pk:
            product.slug = unique_slug_for(Product, product.name)
            product.is_active = True
        if commit:
            product.save()
            self.save_m2m()
        return product


class CategoryNameForm(forms.Form):
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
        siblings = Category.objects.filter(parent=self.parent, name__iexact=name)
        if self.instance:
            siblings = siblings.exclude(pk=self.instance.pk)
        if siblings.exists():
            raise ValidationError("A category with this name already exists here.")
        return name

    def save(self):
        category = self.instance or Category(parent=self.parent, is_active=True)
        category.name = self.cleaned_data["name"]
        if not category.pk:
            category.slug = unique_slug_for(Category, category.name)
        category.save()
        return category


class InventoryUpdateForm(forms.ModelForm):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = InventoryRecord
        fields = ["current_stock", "low_stock_threshold"]


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status"]


class UserManageForm(forms.Form):
    full_name = forms.CharField(max_length=140)
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=24, required=False)
    password = forms.CharField(required=False, widget=forms.PasswordInput)
    confirm_password = forms.CharField(required=False, widget=forms.PasswordInput)
    is_active = forms.BooleanField(required=False, initial=True, label="Active")

    role = None

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if instance:
            self.fields["full_name"].initial = instance.get_full_name() or instance.username
            self.fields["username"].initial = instance.username
            self.fields["email"].initial = instance.email
            self.fields["is_active"].initial = instance.is_active
            self.fields["password"].help_text = "Leave blank to keep the current password."
            self.fields["confirm_password"].help_text = "Required only when resetting password."
            profile = getattr(instance, "profile", None)
            if profile:
                self.fields["phone"].initial = profile.phone

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        users = User.objects.filter(username__iexact=username)
        if self.instance:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if email:
            users = User.objects.filter(email__iexact=email)
            if self.instance:
                users = users.exclude(pk=self.instance.pk)
            if users.exists():
                raise ValidationError("Email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if not self.instance and not password:
            self.add_error("password", "Password is required.")
        if password and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned

    def save(self, created_by=None):
        user = self.instance or User()
        names = self.cleaned_data["full_name"].strip().split(" ", 1)
        user.first_name = names[0]
        user.last_name = names[1] if len(names) > 1 else ""
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.is_active = self.cleaned_data.get("is_active", False)
        if self.role == UserProfile.STAFF:
            user.is_staff = False
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = self.role
        profile.phone = self.cleaned_data.get("phone", "")
        profile.save()
        return user


class EmployeeManageForm(UserManageForm):
    role = UserProfile.STAFF

    def save(self, created_by=None):
        user = super().save(created_by=created_by)
        StaffProfile.objects.get_or_create(user=user, defaults={"created_by": created_by})
        return user


class AgentManageForm(UserManageForm):
    role = UserProfile.AGENT
    agent_code = forms.CharField(max_length=20, required=False, help_text="Leave blank to generate automatically.")
    discount_percentage = forms.DecimalField(
        label="Discount Percentage",
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        help_text="Enter a value from 0 to 100.",
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        if instance and hasattr(instance, "agent_profile"):
            self.fields["agent_code"].initial = instance.agent_profile.agent_code
            self.fields["discount_percentage"].initial = instance.agent_profile.discount_percentage

    def clean_agent_code(self):
        code = self.cleaned_data.get("agent_code", "").strip().upper()
        if code:
            profiles = AgentProfile.objects.filter(agent_code__iexact=code)
            if self.instance and hasattr(self.instance, "agent_profile"):
                profiles = profiles.exclude(pk=self.instance.agent_profile.pk)
            if profiles.exists():
                raise ValidationError("Agent code already exists.")
        return code

    def save(self, created_by=None):
        user = super().save(created_by=created_by)
        agent_profile, _ = AgentProfile.objects.get_or_create(user=user, defaults={"created_by": created_by})
        if self.cleaned_data.get("agent_code"):
            agent_profile.agent_code = self.cleaned_data["agent_code"]
        agent_profile.discount_percentage = self.cleaned_data.get("discount_percentage") or Decimal("0.00")
        agent_profile.save(update_fields=["agent_code", "discount_percentage", "updated_at"])
        return user
