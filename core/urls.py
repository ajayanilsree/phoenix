from django.urls import path

from .views import about, home, robots_txt

urlpatterns = [
    path("", home, name="home"),
    path("about/", about, name="about"),
    path("robots.txt", robots_txt, name="robots_txt"),
]
