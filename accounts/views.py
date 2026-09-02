import hashlib
import logging
import secrets
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .decorators import user_role
from .forms import CustomerPasswordResetRequestForm, CustomerRegistrationForm, CustomerSetPasswordForm, PhoenixLoginForm
from .models import UserProfile
from .services.email_service import send_password_reset_otp

logger = logging.getLogger(__name__)
RESET_REQUEST_MESSAGE = "If the details match an account, password reset instructions have been sent to the registered email address."
RESET_RATE_LIMIT_SECONDS = 300
OTP_TTL_SECONDS = 600
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_USER_SESSION_KEY = "password_reset_user_id"
OTP_HASH_SESSION_KEY = "password_reset_otp_hash"
OTP_EXPIRES_SESSION_KEY = "password_reset_otp_expires"
OTP_ATTEMPTS_SESSION_KEY = "password_reset_otp_attempts"
OTP_SENT_SESSION_KEY = "password_reset_otp_sent"
OTP_VERIFIED_SESSION_KEY = "password_reset_otp_verified"


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


def _reset_rate_key(request, form):
    value = f"{form.cleaned_data.get('username', '').casefold()}:{form.cleaned_data.get('email', '').casefold()}:{request.META.get('REMOTE_ADDR', '')}"
    return "password-reset:" + hashlib.sha256(value.encode()).hexdigest()


def _clear_otp_session(request):
    for key in [OTP_USER_SESSION_KEY, OTP_HASH_SESSION_KEY, OTP_EXPIRES_SESSION_KEY, OTP_ATTEMPTS_SESSION_KEY, OTP_SENT_SESSION_KEY, OTP_VERIFIED_SESSION_KEY]:
        request.session.pop(key, None)


def _create_otp(request, user):
    otp = f"{secrets.randbelow(1_000_000):06d}"
    request.session[OTP_USER_SESSION_KEY] = user.pk
    request.session[OTP_HASH_SESSION_KEY] = make_password(otp)
    request.session[OTP_EXPIRES_SESSION_KEY] = time.time() + OTP_TTL_SECONDS
    request.session[OTP_ATTEMPTS_SESSION_KEY] = 0
    request.session[OTP_SENT_SESSION_KEY] = time.time()
    request.session[OTP_VERIFIED_SESSION_KEY] = False
    return otp


def _pending_customer(request):
    user_id = request.session.get(OTP_USER_SESSION_KEY)
    if not user_id:
        return None
    return UserProfile.objects.select_related("user").filter(
        user_id=user_id,
        role=UserProfile.CUSTOMER,
        is_active_customer=True,
        user__is_active=True,
    ).first()


@never_cache
@require_http_methods(["GET", "POST"])
def forgot_password(request):
    form = CustomerPasswordResetRequestForm(request.POST or None)
    submitted = False
    if request.method == "POST" and form.is_valid():
        submitted = True
        if cache.add(_reset_rate_key(request, form), True, RESET_RATE_LIMIT_SECONDS):
            profile = UserProfile.objects.select_related("user").filter(
                role=UserProfile.CUSTOMER,
                is_active_customer=True,
                user__is_active=True,
                user__username__iexact=form.cleaned_data["username"],
                user__email__iexact=form.cleaned_data["email"],
            ).first()
            if profile:
                otp = _create_otp(request, profile.user)
                try:
                    send_password_reset_otp(profile.user, otp)
                except Exception:
                    _clear_otp_session(request)
                    logger.exception("Password reset OTP delivery failed for a customer account.")
                    return render(request, "accounts/forgot_password.html", {"form": form, "email_error": "We could not send the verification email right now. Please try again shortly."})
                return redirect("verify_otp")
    return render(request, "accounts/forgot_password.html", {"form": form, "submitted": submitted, "reset_message": RESET_REQUEST_MESSAGE})


@never_cache
@require_http_methods(["GET", "POST"])
def verify_otp(request):
    profile = _pending_customer(request)
    if not profile:
        return redirect("forgot_password")
    error = ""
    if request.method == "POST":
        if time.time() > request.session.get(OTP_EXPIRES_SESSION_KEY, 0):
            error = "Verification code has expired. Please request a new code."
        elif request.session.get(OTP_ATTEMPTS_SESSION_KEY, 0) >= OTP_MAX_ATTEMPTS:
            error = "Too many incorrect attempts. Please request a new code."
        elif check_password(request.POST.get("otp", "").strip(), request.session.get(OTP_HASH_SESSION_KEY, "")):
            request.session[OTP_VERIFIED_SESSION_KEY] = True
            request.session.pop(OTP_HASH_SESSION_KEY, None)
            request.session.pop(OTP_ATTEMPTS_SESSION_KEY, None)
            return redirect("reset_password")
        else:
            request.session[OTP_ATTEMPTS_SESSION_KEY] = request.session.get(OTP_ATTEMPTS_SESSION_KEY, 0) + 1
            error = "That verification code is incorrect."
    return render(request, "accounts/verify_otp.html", {"error": error, "expires_at": request.session.get(OTP_EXPIRES_SESSION_KEY, 0), "resend_available_at": request.session.get(OTP_SENT_SESSION_KEY, 0) + OTP_RESEND_COOLDOWN_SECONDS})


@never_cache
@require_http_methods(["POST"])
def resend_otp(request):
    profile = _pending_customer(request)
    if not profile:
        return redirect("forgot_password")
    if time.time() < request.session.get(OTP_SENT_SESSION_KEY, 0) + OTP_RESEND_COOLDOWN_SECONDS:
        messages.error(request, "Please wait before requesting another code.")
        return redirect("verify_otp")
    otp = _create_otp(request, profile.user)
    try:
        send_password_reset_otp(profile.user, otp)
    except Exception:
        _clear_otp_session(request)
        logger.exception("Password reset OTP resend failed for a customer account.")
        messages.error(request, "We could not send the verification email right now. Please try again shortly.")
        return redirect("forgot_password")
    messages.success(request, "A new verification code has been sent.")
    return redirect("verify_otp")


@never_cache
@require_http_methods(["GET", "POST"])
def reset_password(request):
    profile = _pending_customer(request)
    if not profile or not request.session.get(OTP_VERIFIED_SESSION_KEY):
        return redirect("forgot_password")
    user = profile.user
    form = CustomerSetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _clear_otp_session(request)
        messages.success(request, "Password updated successfully. You can now log in with your new password.")
        return redirect("login")
    return render(request, "accounts/reset_password.html", {"form": form})


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
