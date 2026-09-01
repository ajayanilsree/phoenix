from .models import Category
from django.db.models import Prefetch


def category_navigation(request):
    children = Category.objects.filter(is_active=True).order_by("sort_order", "name")
    return {
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related(Prefetch("children", queryset=children, to_attr="nav_children"))
        .order_by("sort_order", "name"),
    }
