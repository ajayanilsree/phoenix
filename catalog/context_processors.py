from .models import Category
from django.db.models import Prefetch
from django.conf import settings


def public_site_url(request):
    configured_url = (getattr(settings, "PUBLIC_SITE_URL", "") or "").rstrip("/")
    local_hosts = ("http://127.0.0.1", "http://localhost", "http://0.0.0.0")
    if not configured_url or configured_url.lower().startswith(local_hosts):
        configured_url = "https://www.phoenixinteriorhub.com"
    return {"public_site_url": configured_url}


def category_navigation(request):
    children = Category.objects.filter(is_active=True).order_by("sort_order", "name")
    return {
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related(Prefetch("children", queryset=children, to_attr="nav_children"))
        .order_by("sort_order", "name"),
    }
