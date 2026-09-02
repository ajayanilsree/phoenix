import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


load_local_env()

DEBUG = env_bool("DEBUG", True)
IS_RENDER = env_bool("RENDER", False) or bool(os.environ.get("RENDER_EXTERNAL_HOSTNAME"))
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-change-me"
    else:
        raise RuntimeError("SECRET_KEY must be configured when DEBUG=False.")

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver", "phoenixinteriorhub.com", "www.phoenixinteriorhub.com", "phoenix-interior-hub.onrender.com"]
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "catalog",
    "inventory",
    "cart",
    "orders",
    "customers",
    "agents",
    "staff_portal",
    "dashboard",
    "chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "phoenix_ecommerce.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cart.context_processors.cart_summary",
                "catalog.context_processors.category_navigation",
                "chatbot.context_processors.chatbot_settings",
            ],
        },
    }
]

WSGI_APPLICATION = "phoenix_ecommerce.wsgi.application"

database_url = os.environ.get("DATABASE_URL")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif IS_RENDER or not DEBUG:
    raise RuntimeError(
        "DATABASE_URL must be configured for Render/production. "
        "Refusing to fall back to disposable SQLite storage."
    )
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploaded media belongs in durable object storage on Render. Keep static files
# on Django's existing filesystem/static deployment path.
CLOUDINARY_CONFIGURED = bool(os.environ.get("CLOUDINARY_URL"))
if CLOUDINARY_CONFIGURED:
    INSTALLED_APPS.append("cloudinary")
    CLOUDINARY_STORAGE = {
        "PREFIX": "phoenix-interior-hub",
        "SECURE": True,
    }
elif not DEBUG:
    raise RuntimeError("CLOUDINARY_URL must be configured when DEBUG=False; uploaded media cannot use Render's local filesystem.")

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage" if CLOUDINARY_CONFIGURED else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "post_login_redirect"
LOGOUT_REDIRECT_URL = "home"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = [
    "https://phoenixinteriorhub.com",
    "https://www.phoenixinteriorhub.com",
    "https://phoenix-interior-hub.onrender.com",
]
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_hostname}")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")
CHATBOT_ENABLED = env_bool("CHATBOT_ENABLED", True)
CHATBOT_MAX_HISTORY = env_int("CHATBOT_MAX_HISTORY", 8)
CHATBOT_MAX_MESSAGE_LENGTH = env_int("CHATBOT_MAX_MESSAGE_LENGTH", 750)

if DEBUG:
    EMAIL_BACKEND = os.environ.get(
        "EMAIL_BACKEND",
        "django.core.mail.backends.console.EmailBackend",
    ).strip()
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp-relay.brevo.com").strip()
EMAIL_PORT = env_int("EMAIL_PORT", 2525)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Phoenix Interior Hub <noreply@phoenixinteriorhub.com>").strip()
EMAIL_TIMEOUT = 10
PUBLIC_SITE_URL = os.environ.get(
    "PUBLIC_SITE_URL",
    "http://127.0.0.1:8000" if DEBUG else "https://www.phoenixinteriorhub.com",
).strip().rstrip("/")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
