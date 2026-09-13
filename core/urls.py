from django.urls import path

from .views import about, home, manifest_webmanifest, robots_txt, service_worker

urlpatterns = [
    path("", home, name="home"),
    path("about/", about, name="about"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("manifest.webmanifest", manifest_webmanifest, name="manifest_webmanifest"),
    path("service-worker.js", service_worker, name="service_worker"),
]
