from django.shortcuts import redirect

from .decorators import user_role


class AdminNamespaceRedirectMiddleware:
    """Keep an admin session in the admin dashboard namespace."""

    prefix_map = {
        "/dashboard/": "/dashboard/",
        "/orders/": "/orders/",
        "/invoices/": "/invoices/",
        "/products/": "/products/",
        "/inventory/": "/inventory/",
        "/services/": "/services/",
        "/service-orders/": "/service-orders/",
        "/login/": "/login/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {"GET", "HEAD"} and request.user.is_authenticated and user_role(request.user) == "admin":
            for source, destination in self.prefix_map.items():
                for namespace in ("/employee", "/staff"):
                    prefix = f"{namespace}{source}"
                    if request.path == prefix or request.path.startswith(prefix):
                        return redirect(f"/admin{destination}{request.path[len(prefix):]}")
        return self.get_response(request)
