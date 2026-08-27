from .models import Category


def category_navigation(request):
    return {
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True).order_by("sort_order", "name")[:5],
    }
