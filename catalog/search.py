from django.db.models import Q


def product_search_query(value, *, include_descriptions=False, include_category=False):
    """Build the shared parent-product search predicate."""
    query = (value or "").strip()
    if not query:
        return Q()

    search = Q(name__icontains=query) | Q(sku__icontains=query) | Q(variants__sku__icontains=query)
    if include_descriptions:
        search |= Q(short_description__icontains=query) | Q(full_description__icontains=query)
    if include_category:
        search |= Q(category__name__icontains=query)
    return search
