from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class PhoenixLoginForm(AuthenticationForm):
    username = forms.CharField(label="Email or username")
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            login_identifier = username
            email_user = User.objects.filter(email__iexact=username).first()
            if email_user:
                login_identifier = email_user.get_username()
            self.user_cache = authenticate(self.request, username=login_identifier, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80, required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "username", "password1", "password2")


class RoleLoginForm(PhoenixLoginForm):
    expected_role = None
    role_label = "this area"

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        role = "admin" if user.is_superuser else getattr(getattr(user, "profile", None), "role", None)
        if self.expected_role == "admin" and role == "admin":
            return
        if role != self.expected_role:
            raise ValidationError(
                "This account does not have access to %(area)s.",
                code="invalid_role",
                params={"area": self.role_label},
            )


class AdminLoginForm(RoleLoginForm):
    expected_role = "admin"
    role_label = "Phoenix Interior Hub Admin"


class EmployeeLoginForm(RoleLoginForm):
    expected_role = "staff"
    role_label = "Employee Dashboard"


class AgentLoginForm(RoleLoginForm):
    expected_role = "agent"
    role_label = "Agent Dashboard"
