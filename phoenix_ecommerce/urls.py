from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include("dashboard.urls")),
    path("api/chatbot/", include("chatbot.urls")),
    path("", include("core.urls")),
    path("", include("catalog.urls")),
    path("", include("cart.urls")),
    path("", include("orders.urls")),
    path("account/", include("customers.urls")),
    path("agent/", include("agents.urls")),
    path("employee/", include("staff_portal.urls")),
    path("staff/", include("staff_portal.urls")),
    path("auth/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
