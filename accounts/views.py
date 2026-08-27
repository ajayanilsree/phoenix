from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .decorators import user_role
from .forms import CustomerRegistrationForm, PhoenixLoginForm


class PhoenixLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = PhoenixLoginForm


class PhoenixLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        self._logout_role = user_role(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        role_redirects = {
            "admin": reverse_lazy("phoenix_admin_login"),
            "staff": reverse_lazy("employee_login"),
            "agent": reverse_lazy("agent_login"),
            "customer": reverse_lazy("home"),
        }
        return role_redirects.get(self._logout_role, reverse_lazy("home"))


def register(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("customer_dashboard")
    else:
        form = CustomerRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def post_login_redirect(request):
    role = user_role(request.user)
    if role == "admin":
        return redirect("admin_dashboard")
    if role == "staff":
        return redirect("employee_dashboard")
    if role == "agent":
        return redirect("agent_dashboard")
    return redirect("customer_dashboard")
